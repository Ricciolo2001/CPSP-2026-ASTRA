import struct
from dataclasses import dataclass

# Packet format (placeholder, change when firmware is defined)
# <  : little-endian
# fff: x, y, yaw as float32
# h  : rssi as int16
# H  : seq as uint16
FMT = "<fffhH"
PKT_SIZE = struct.calcsize(FMT)

@dataclass
class Telemetry:
    x: float
    y: float
    yaw: float
    rssi: int
    seq: int

def unpack_packet(packet: bytes) -> Telemetry:
    if len(packet) != PKT_SIZE:
        raise ValueError(f"Bad packet size: {len(packet)} (expected {PKT_SIZE})")
    x, y, yaw, rssi, seq = struct.unpack(FMT, packet)
    return Telemetry(x=x, y=y, yaw=yaw, rssi=rssi, seq=seq)

def pack_packet(t: Telemetry) -> bytes:
    return struct.pack(FMT, t.x, t.y, t.yaw, t.rssi, t.seq)
