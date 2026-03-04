import csv
import time
from pathlib import Path

from cflib.crazyflie import Crazyflie
from cflib.crtp import init_drivers

from astra.protocol import PKT_SIZE, unpack_packet

URI = "radio://0/80/2M/E7E7E7E7E7"
OUT = Path("telemetry_log.csv")

last_seq = None

def main():
    global last_seq

    init_drivers(enable_debug_driver=False)
    cf = Crazyflie(rw_cache="./cache")

    print(f"Logging to: {OUT.resolve()}")
    f = OUT.open("w", newline="")
    w = csv.writer(f)
    w.writerow(["t", "x", "y", "yaw", "rssi", "seq"])

    def on_packet(packet: bytes):
        nonlocal w
        nonlocal f
        global last_seq

        if len(packet) != PKT_SIZE:
            return

        try:
            t = unpack_packet(packet)
        except Exception:
            return

        # Seq jump warning
        if last_seq is not None:
            expected = (last_seq + 1) % 65536
            if t.seq != expected:
                print(f"[warn] seq jump: {last_seq} -> {t.seq} (expected {expected})")
        last_seq = t.seq

        w.writerow([time.time(), t.x, t.y, t.yaw, t.rssi, t.seq])
        f.flush()

    cf.appchannel.packet_received.add_callback(on_packet)

    print(f"Connecting to {URI}")
    cf.open_link(URI)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing link")
        cf.close_link()
        f.close()

if __name__ == "__main__":
    main()
