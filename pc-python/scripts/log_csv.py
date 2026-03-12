#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from astra.crazyflie_link import AppChannelReceiver
from astra.protocol import Telemetry
from astra.rssi import MedianEmaFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log ASTRA telemetry packets to CSV.")
    parser.add_argument("--uri", default="radio://0/80/2M/E7E7E7E7E7", help="Crazyradio URI")
    parser.add_argument("--out", default="telemetry_log.csv", help="Output CSV path")
    parser.add_argument("--window", type=int, default=5, help="Median filter window size")
    parser.add_argument("--alpha", type=float, default=0.35, help="EMA alpha in (0, 1]")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    filt = MedianEmaFilter(window_size=args.window, alpha=args.alpha)
    receiver = AppChannelReceiver(args.uri)

    with output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "yaw", "rssi_raw", "rssi_filtered", "seq"])

        def on_telemetry(t: Telemetry) -> None:
            rssi_filtered = filt.update(t.rssi)
            writer.writerow([time.time(), t.x, t.y, t.yaw, t.rssi, f"{rssi_filtered:.3f}", t.seq])
            f.flush()
            print(
                f"logged seq={t.seq:5d} pos=({t.x:7.3f}, {t.y:7.3f}) "
                f"yaw={t.yaw:7.3f} rssi={t.rssi:4d} filt={rssi_filtered:7.3f}"
            )

        print(f"Connecting to {args.uri}")
        print(f"Logging to: {output.resolve()}")
        try:
            receiver.run(on_telemetry)
        except KeyboardInterrupt:
            receiver.stop()
            print("\nClosing link")
            print(
                f"Packets received: {receiver.stats.received_packets} | "
                f"Dropped(seq estimate): {receiver.stats.dropped_packets} | "
                f"Bad packets: {receiver.stats.bad_packets}"
            )


if __name__ == "__main__":
    main()
