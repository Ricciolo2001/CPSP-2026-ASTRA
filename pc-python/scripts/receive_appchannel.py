import time

from cflib.crazyflie import Crazyflie
from cflib.crtp import init_drivers

from astra.protocol import PKT_SIZE, unpack_packet

# TODO: put your real URI
URI = "radio://0/80/2M/E7E7E7E7E7"

last_seq = None


def on_packet(packet: bytes):
    global last_seq

    # Debug if firmware sends variable-length / text packets at the beginning
    if len(packet) != PKT_SIZE:
        print(f"[dbg] packet len={len(packet)} first_bytes={packet[:16]!r}")
        return

    try:
        t = unpack_packet(packet)
    except Exception as e:
        print(f"[err] unpack failed: {e}")
        return

    # Seq jump warning
    if last_seq is not None:
        expected = (last_seq + 1) % 65536
        if t.seq != expected:
            print(f"[warn] seq jump: {last_seq} -> {t.seq} (expected {expected})")
    last_seq = t.seq

    print(f"x={t.x:.3f} y={t.y:.3f} yaw={t.yaw:.3f} rssi={t.rssi} seq={t.seq}")


def main():
    init_drivers(enable_debug_driver=False)

    cf = Crazyflie(rw_cache="./cache")
    cf.appchannel.packet_received.add_callback(on_packet)

    print(f"Connecting to {URI}")
    cf.open_link(URI)

    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing link")
        cf.close_link()


if __name__ == "__main__":
    main()
