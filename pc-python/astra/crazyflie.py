# Functions related to the Crazyflie

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Callable

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crtp.crtpstack import CRTPPacket

from .protocol import (
    CRTP_APP_PORT,
    CMD_DISTANCE,
    Telemetry,
)

# CRTP packets carry at most 30 bytes of payload
CRTP_MAX_PAYLOAD = 30


# ---------------------------------------------------------------------------
# Low-level transport helpers (chunked text over a single CRTP port)
# ---------------------------------------------------------------------------


def send(cf: Crazyflie, port: int, data: bytes) -> None:
    """
    Send *data* as one or more CRTP packets of at most CRTP_MAX_PAYLOAD
    bytes each.
    """
    for offset in range(0, len(data), CRTP_MAX_PAYLOAD):
        chunk = data[offset : offset + CRTP_MAX_PAYLOAD]
        pk = CRTPPacket()
        pk.port = port
        pk.channel = 0
        pk.data = chunk
        cf.send_packet(pk)


def send_line(cf: Crazyflie, port: int, line: str) -> None:
    """
    Encode *line* as UTF-8, append a newline terminator, then send it as
    one or more CRTP packets of at most CRTP_MAX_PAYLOAD bytes each.
    """
    data = (line + "\n").encode("utf-8")
    send(cf, port, data)


class LineAssembler:
    """
    Accumulates raw bytes arriving in individual CRTP packets and emits
    complete lines (split on '\\n') via *on_line*.
    """

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self._buf = bytearray()
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, packet: CRTPPacket) -> None:
        with self._lock:
            self._buf.extend(bytes(packet.data))
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("latin-1")
                self._on_line(text)


class FirmwareLogAssembler:
    """
    Receives raw character chunks from cf.console.receivedChar (which fires
    with arbitrary UTF-8 fragments, not full lines) and emits complete lines
    via *on_line*.
    """

    def __init__(self, on_line: Callable[[str], None]) -> None:
        self._buf = ""
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, text: str) -> None:
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._on_line(line)


# ---------------------------------------------------------------------------
# Link statistics
# ---------------------------------------------------------------------------


@dataclass
class LinkStats:
    received_samples: int = 0
    missing_position: int = 0
    missing_rssi: int = 0
    bad_responses: int = 0


# ---------------------------------------------------------------------------
# High-level link: CRTP text commands + cflib log for drone position
# ---------------------------------------------------------------------------


class AstraLink:
    """
    Manages the connection to an ASTRA Crazyflie.

    * Drone **position** (x, y, yaw) is streamed via the cflib log framework
      (stateEstimate variables at 10 Hz).
    * Beacon **RSSI** is obtained by periodically sending a DISTANCE command
      over CRTP port *port* and parsing the JSON reply.

    Usage::

        link = AstraLink(uri="radio://0/80/2M/E7E7E7E7E7",
                         beacon_addr="AA:BB:CC:DD:EE:FF")
        try:
            link.run(on_telemetry)   # blocks until KeyboardInterrupt or link.stop()
        except KeyboardInterrupt:
            link.stop()
    """

    _LOG_PERIOD_MS = 100  # position log period (10 Hz)

    def __init__(
        self,
        uri: str,
        beacon_addr: str,
        port: int = CRTP_APP_PORT,
        poll_interval: float = 0.5,
    ) -> None:
        self.uri = uri
        self.beacon_addr = beacon_addr
        self.port = port
        self.poll_interval = poll_interval
        self.stats = LinkStats()

        self._stop = threading.Event()
        self._latest_pos: tuple[float, float, float] | None = None
        self._pos_lock = threading.Lock()
        self._pending_rssi: int | None = None
        self._rssi_event = threading.Event()
        self._bind_event = threading.Event()

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_position_log(
        self,
        _timestamp: int,
        data: dict,
        _logconf: LogConfig,
    ) -> None:
        with self._pos_lock:
            self._latest_pos = (
                float(data["stateEstimate.x"]),
                float(data["stateEstimate.y"]),
                float(data["stateEstimate.yaw"]),
            )

    def _on_line(self, text: str) -> None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            self.stats.bad_responses += 1
            return

        result = data.get("result")

        if isinstance(result, str):
            # BIND acknowledgement — firmware confirmed the bind
            self._bind_event.set()
        elif result is not None:
            # DISTANCE response — firmware returned a numeric RSSI value
            try:
                self._pending_rssi = int(result)
                self._rssi_event.set()
            except (TypeError, ValueError):
                self.stats.bad_responses += 1
        else:
            self.stats.bad_responses += 1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, callback: Callable[[Telemetry], None]) -> None:
        """
        Connect to the Crazyflie, bind to the beacon, and start polling.
        Calls *callback* with a :class:`~astra.protocol.Telemetry` sample
        each time both a fresh RSSI value and a valid position are available.

        Blocks until :meth:`stop` is called or the link is lost.
        """
        cflib.crtp.init_drivers(enable_debug_driver=False)

        cf = Crazyflie(rw_cache="./cache")
        with SyncCrazyflie(self.uri, cf=cf) as scf:
            # --- position log -------------------------------------------
            log_conf = LogConfig(name="AstraPosition", period_in_ms=self._LOG_PERIOD_MS)
            log_conf.add_variable("stateEstimate.x", "float")
            log_conf.add_variable("stateEstimate.y", "float")
            log_conf.add_variable("stateEstimate.yaw", "float")
            log_conf.data_received_cb.add_callback(self._on_position_log)
            scf.cf.log.add_config(log_conf)
            log_conf.start()

            # --- CRTP text channel ---------------------------------------
            assembler = LineAssembler(self._on_line)
            scf.cf.add_port_callback(self.port, assembler.feed)

            # Bind to the target beacon and wait for acknowledgement
            self._bind_event.clear()
            send_line(scf.cf, self.port, cmd_bind(self.beacon_addr))
            if not self._bind_event.wait(timeout=5.0):
                raise RuntimeError(
                    f"BIND timed out: no acknowledgement from firmware "
                    f"for beacon {self.beacon_addr!r}"
                )

            try:
                while not self._stop.is_set():
                    # Request a fresh RSSI reading
                    self._rssi_event.clear()
                    send_line(scf.cf, self.port, CMD_DISTANCE)

                    # Wait for the reply (at most 2× the poll interval)
                    got_reply = self._rssi_event.wait(timeout=self.poll_interval * 2)

                    if not got_reply or self._pending_rssi is None:
                        self.stats.missing_rssi += 1
                        self._stop.wait(self.poll_interval)
                        continue

                    rssi = self._pending_rssi
                    self._pending_rssi = None

                    with self._pos_lock:
                        pos = self._latest_pos

                    if pos is None:
                        self.stats.missing_position += 1
                        self._stop.wait(self.poll_interval)
                        continue

                    x, y, yaw = pos
                    self.stats.received_samples += 1
                    callback(Telemetry(x=x, y=y, yaw=yaw, rssi=rssi))

                    self._stop.wait(self.poll_interval)

            finally:
                log_conf.stop()
                scf.cf.remove_port_callback(self.port, assembler.feed)

    def stop(self) -> None:
        """Signal the polling loop to exit."""
        self._stop.set()
