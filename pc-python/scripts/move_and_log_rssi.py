#!/usr/bin/env python3
"""
Test/move script for Astra firmware.

Fa:
1) connessione al Crazyflie via URI
2) bind al beacon BLE
3) ascolto dei log di posizione
4) lettura ultima posizione valida
5) movimento di +1 o -1 lungo asse scelto
6) polling RSSI durante il movimento
7) salvataggio CSV

Esempio:
    python move_with_rssi.py \
        --uri radio://0/80/2M/E7E7E7E7E7 \
        --beacon AA:BB:CC:DD:EE:FF \
        --axis x \
        --delta 1 \
        --out move_rssi.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crtp.crtpstack import CRTPPacket

logging.basicConfig(level=logging.ERROR)

DEFAULT_URI = "radio://0/80/2M/E7E7E7E7E7"
CRTP_APP_PORT = 0x0E
CMD_DISTANCE = "DISTANCE"
CRTP_MAX_PAYLOAD = 30
LOG_PERIOD_MS = 100


def cmd_bind(addr: str) -> str:
    return f"BIND {addr}"


def normalize_beacon_addr(addr: str) -> str:
    raw = addr.replace(":", "").replace("-", "").strip()
    if len(raw) != 12 or any(c not in "0123456789abcdefABCDEF" for c in raw):
        raise ValueError(
            "Beacon address must be exactly 12 hex characters "
            "(example: AA:BB:CC:DD:EE:FF)"
        )
    raw = raw.upper()
    return ":".join(raw[i:i + 2] for i in range(0, 12, 2))


def send_line(cf: Crazyflie, port: int, line: str) -> None:
    """Send one text command over CRTP, chunked at 30 bytes."""
    data = (line + "\n").encode("utf-8")
    for offset in range(0, len(data), CRTP_MAX_PAYLOAD):
        chunk = data[offset: offset + CRTP_MAX_PAYLOAD]
        pk = CRTPPacket()
        pk.port = port
        pk.channel = 0
        pk.data = chunk
        cf.send_packet(pk)


class LineAssembler:
    """Reassembles newline-terminated text lines from CRTP packet fragments."""

    def __init__(self, on_line):
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


@dataclass
class PositionState:
    x: float
    y: float
    z: float
    yaw: float
    timestamp_s: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bind beacon, read last position, move +/-1, log RSSI"
    )
    parser.add_argument(
        "--uri",
        default=DEFAULT_URI,
        help="Crazyflie radio URI (default: %(default)s)",
    )
    parser.add_argument(
        "--beacon",
        required=True,
        help="BLE beacon address (example: AA:BB:CC:DD:EE:FF)",
    )
    parser.add_argument(
        "--axis",
        choices=["x", "y"],
        default="x",
        help="Axis for the motion command",
    )
    parser.add_argument(
        "--delta",
        type=float,
        choices=[-1.0, 1.0],
        default=1.0,
        help="Movement delta in meters: +1 or -1",
    )
    parser.add_argument(
        "--move-time",
        type=float,
        default=3.0,
        help="How long to stream the target setpoint [s]",
    )
    parser.add_argument(
        "--hold-time",
        type=float,
        default=1.0,
        help="How long to hold the final target [s]",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=0.2,
        help="RSSI polling interval [s]",
    )
    parser.add_argument(
        "--setpoint-rate",
        type=float,
        default=10.0,
        help="Position setpoint streaming rate [Hz]",
    )
    parser.add_argument(
        "--out",
        default="move_rssi.csv",
        help="Output CSV path",
    )
    return parser.parse_args()


def run_astra_session(scf: SyncCrazyflie, beacon_addr: str, args: argparse.Namespace) -> None:
    cf = scf.cf
    latest_pos: PositionState | None = None
    pos_lock = threading.Lock()
    bind_ack = threading.Event()

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    def on_position_log(_timestamp: int, data: dict, _logconf: LogConfig) -> None:
        nonlocal latest_pos
        state = PositionState(
            x=float(data["stateEstimate.x"]),
            y=float(data["stateEstimate.y"]),
            z=float(data["stateEstimate.z"]),
            yaw=float(data["stateEstimate.yaw"]),
            timestamp_s=time.time(),
        )
        with pos_lock:
            latest_pos = state

    with output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "z", "yaw", "rssi_raw"])

        def on_app_line(text: str) -> None:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                print(f"[warning] Invalid JSON from firmware: {text!r}")
                return

            result = payload.get("result")

            if isinstance(result, str):
                # ACK del BIND
                bind_ack.set()
                return

            if result is None:
                print(f"[warning] Unexpected firmware response: {text!r}")
                return

            try:
                rssi = int(result)
            except (TypeError, ValueError):
                print(f"[warning] Non-integer RSSI: {result!r}")
                return

            with pos_lock:
                st = latest_pos

            if st is None:
                return

            now = time.time()
            writer.writerow([now, st.x, st.y, st.z, st.yaw, rssi])
            f.flush()

            print(
                f"t={now:.3f}  pos=({st.x:.3f}, {st.y:.3f}, {st.z:.3f})  "
                f"yaw={st.yaw:.2f}  rssi={rssi} dBm"
            )

        # Position log config
        log_conf = LogConfig(name="AstraPosition", period_in_ms=LOG_PERIOD_MS)
        log_conf.add_variable("stateEstimate.x", "float")
        log_conf.add_variable("stateEstimate.y", "float")
        log_conf.add_variable("stateEstimate.z", "float")
        log_conf.add_variable("stateEstimate.yaw", "float")
        log_conf.data_received_cb.add_callback(on_position_log)

        assembler = LineAssembler(on_app_line)

        cf.log.add_config(log_conf)
        log_conf.start()
        cf.add_port_callback(CRTP_APP_PORT, assembler.feed)

        try:
            print(f"Binding beacon → {beacon_addr}")
            bind_ack.clear()
            send_line(cf, CRTP_APP_PORT, cmd_bind(beacon_addr))

            if not bind_ack.wait(timeout=5.0):
                raise RuntimeError(
                    f"BIND timeout: no acknowledgement from firmware for {beacon_addr}"
                )

            print("Bind OK. Waiting for a valid position sample...")

            t0 = time.time()
            while True:
                with pos_lock:
                    st = latest_pos
                if st is not None:
                    break
                if time.time() - t0 > 5.0:
                    raise RuntimeError("No valid position received from stateEstimate.*")
                time.sleep(0.05)

            assert st is not None
            x0, y0, z0, yaw0 = st.x, st.y, st.z, st.yaw

            if args.axis == "x":
                target_x = x0 + args.delta
                target_y = y0
            else:
                target_x = x0
                target_y = y0 + args.delta

            target_z = z0
            target_yaw = yaw0

            print(
                f"Last position  : x={x0:.3f}, y={y0:.3f}, z={z0:.3f}, yaw={yaw0:.2f}"
            )
            print(
                f"Move target    : x={target_x:.3f}, y={target_y:.3f}, "
                f"z={target_z:.3f}, yaw={target_yaw:.2f}"
            )
            print("Streaming setpoints and polling RSSI...")

            dt_setpoint = 1.0 / args.setpoint_rate
            next_rssi_poll = 0.0
            t_start = time.time()

            # Fase movimento
            while True:
                now = time.time()
                elapsed = now - t_start
                if elapsed >= args.move_time:
                    break

                cf.commander.send_position_setpoint(
                    target_x,
                    target_y,
                    target_z,
                    target_yaw,
                )

                if now >= next_rssi_poll:
                    send_line(cf, CRTP_APP_PORT, CMD_DISTANCE)
                    next_rssi_poll = now + args.poll

                time.sleep(dt_setpoint)

            # Fase hold
            print("Holding final target...")
            t_hold = time.time()
            while time.time() - t_hold < args.hold_time:
                cf.commander.send_position_setpoint(
                    target_x,
                    target_y,
                    target_z,
                    target_yaw,
                )
                send_line(cf, CRTP_APP_PORT, CMD_DISTANCE)
                time.sleep(max(dt_setpoint, args.poll))

            cf.commander.send_stop_setpoint()
            print(f"Done. CSV saved to: {output.resolve()}")

        finally:
            try:
                log_conf.stop()
            except Exception:
                pass
            try:
                cf.remove_port_callback(CRTP_APP_PORT, assembler.feed)
            except Exception:
                pass


if __name__ == "__main__":
    args = parse_args()
    beacon_addr = normalize_beacon_addr(args.beacon)

    cflib.crtp.init_drivers(enable_debug_driver=False)

    print(f"Connecting to {args.uri}")
    print(f"Beacon: {beacon_addr}")

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        run_astra_session(scf, beacon_addr, args)