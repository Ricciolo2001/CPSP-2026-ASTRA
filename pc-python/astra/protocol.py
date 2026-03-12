import struct
from dataclasses import dataclass

# Default packet format currently aligned with the placeholder already present in
# the repository. Update this if the firmware sends a different payload.
# <      little-endian
# f f f  x, y, yaw   as float32
# h      rssi        as int16
# H      seq         as uint16
DEFAULT_FMT = "<fffhH"
PKT_SIZE = struct.calcsize(DEFAULT_FMT)


@dataclass(slots=True)
class Telemetry:
    x: float
    y: float
    yaw: float
    rssi: int
    seq: int


class PacketError(ValueError):
    pass


def unpack_packet(packet: bytes, fmt: str = DEFAULT_FMT) -> Telemetry:
    expected = struct.calcsize(fmt)
    if len(packet) != expected:
        raise PacketError(f"Bad packet size: {len(packet)} (expected {expected})")

    x, y, yaw, rssi, seq = struct.unpack(fmt, packet)
    return Telemetry(x=float(x), y=float(y), yaw=float(yaw), rssi=int(rssi), seq=int(seq))


def pack_packet(t: Telemetry, fmt: str = DEFAULT_FMT) -> bytes:
    return struct.pack(fmt, t.x, t.y, t.yaw, t.rssi, t.seq)
