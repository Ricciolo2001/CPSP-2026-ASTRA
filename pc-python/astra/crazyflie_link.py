from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from cflib.crazyflie import Crazyflie
from cflib.crtp import init_drivers

from .protocol import PKT_SIZE, Telemetry, unpack_packet


@dataclass(slots=True)
class LinkStats:
    received_packets: int = 0
    dropped_packets: int = 0
    bad_packets: int = 0
    last_seq: int | None = None


class AppChannelReceiver:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.cf = Crazyflie(rw_cache="./cache")
        self.stats = LinkStats()
        self._stop = threading.Event()

    def _handle_packet(self, packet: bytes, callback: Callable[[Telemetry], None]) -> None:
        if len(packet) != PKT_SIZE:
            self.stats.bad_packets += 1
            return

        try:
            telemetry = unpack_packet(packet)
        except Exception:
            self.stats.bad_packets += 1
            return

        if self.stats.last_seq is not None:
            expected = (self.stats.last_seq + 1) % 65536
            if telemetry.seq != expected:
                delta = (telemetry.seq - expected) % 65536
                self.stats.dropped_packets += delta
        self.stats.last_seq = telemetry.seq
        self.stats.received_packets += 1
        callback(telemetry)

    def run(self, callback: Callable[[Telemetry], None], sleep_s: float = 0.2) -> None:
        init_drivers(enable_debug_driver=False)
        self.cf.appchannel.packet_received.add_callback(lambda packet: self._handle_packet(packet, callback))
        self.cf.open_link(self.uri)
        try:
            while not self._stop.is_set():
                time.sleep(sleep_s)
        finally:
            self.cf.close_link()

    def stop(self) -> None:
        self._stop.set()
