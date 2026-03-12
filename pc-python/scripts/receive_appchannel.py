#!/usr/bin/env python3
from __future__ import annotations

import argparse

from astra.crazyflie_link import AppChannelReceiver
from astra.protocol import Telemetry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Receive and print ASTRA telemetry packets from Crazyflie AppChannel.")
    parser.add_argument("--uri", default="radio://0/80/2M/E7E7E7E7E7", help="Crazyradio URI")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    receiver = AppChannelReceiver(args.uri)

    def on_telemetry(t: Telemetry) -> None:
        print(f"x={t.x:.3f} y={t.y:.3f} yaw={t.yaw:.3f} rssi={t.rssi} seq={t.seq}")

    print(f"Connecting to {args.uri}")
    try:
        receiver.run(on_telemetry)
    except KeyboardInterrupt:
        receiver.stop()
        print("\nClosing link")


if __name__ == "__main__":
    main()
