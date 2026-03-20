#!/usr/bin/env python3
"""
log_csv.py — Connect to a Crazyflie, bind to a BLE beacon, and log telemetry
samples (drone position + beacon RSSI) to a CSV file for later analysis.

Usage:
    python scripts/log_csv.py --uri radio://0/80/2M/E7E7E7E7E7 --beacon AA:BB:CC:DD:EE:FF
    python scripts/log_csv.py --uri radio://0/80/2M/E7E7E7E7E7 --beacon AA:BB:CC:DD:EE:FF --out flight.csv
"""
from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from astra.crazyflie_link import AstraLink
from astra.protocol import Telemetry
from astra.rssi import MedianEmaFilter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log ASTRA telemetry to CSV.")
    parser.add_argument(
        "--uri", default="radio://0/80/2M/E7E7E7E7E7", help="Crazyradio URI"
    )
    parser.add_argument(
        "--beacon",
        required=True,
        help="BLE beacon address to track (e.g. AA:BB:CC:DD:EE:FF)",
    )
    parser.add_argument("--out", default="telemetry_log.csv", help="Output CSV path")
    parser.add_argument(
        "--poll", type=float, default=0.5, help="DISTANCE poll interval in seconds"
    )
    parser.add_argument(
        "--window", type=int, default=5, help="Median filter window size"
    )
    parser.add_argument("--alpha", type=float, default=0.35, help="EMA alpha in (0, 1]")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    filt = MedianEmaFilter(window_size=args.window, alpha=args.alpha)
    link = AstraLink(
        uri=args.uri,
        beacon_addr=args.beacon,
        poll_interval=args.poll,
    )

    with output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t", "x", "y", "yaw", "rssi_raw", "rssi_filtered"])

        def on_telemetry(t: Telemetry) -> None:
            rssi_filtered = filt.update(t.rssi)
            writer.writerow(
                [
                    time.time(),
                    t.x,
                    t.y,
                    t.yaw,
                    t.rssi,
                    f"{rssi_filtered:.3f}",
                ]
            )
            f.flush()
            print(
                f"logged  pos=({t.x:7.3f}, {t.y:7.3f})  "
                f"yaw={t.yaw:7.3f}  rssi={t.rssi:4d}  filt={rssi_filtered:7.3f}"
            )

        print(f"Connecting to {args.uri}")
        print(f"Beacon: {args.beacon}")
        print(f"Logging to: {output.resolve()}")
        try:
            link.run(on_telemetry)
        except KeyboardInterrupt:
            link.stop()
            print("\nClosing link")
            print(
                f"Samples received : {link.stats.received_samples}\n"
                f"Missing RSSI     : {link.stats.missing_rssi}\n"
                f"Missing position : {link.stats.missing_position}\n"
                f"Bad responses    : {link.stats.bad_responses}"
            )


if __name__ == "__main__":
    main()
