#!/usr/bin/env python3
"""
scan.py — Discover nearby BLE beacons via the ASTRA Crazyflie firmware.

Connects to the Crazyflie, sends a SCAN command, and continuously prints
the list of discovered BLE device addresses as they arrive.  Each scan is
automatically re-triggered after the firmware replies, so the list refreshes
in a loop until the user interrupts with Ctrl-C.

The beacon address printed here is the value to pass as --beacon to
receive_appchannel.py and log_csv.py.

Usage:
    python scripts/scan.py --uri radio://0/80/2M/E7E7E7E7E7
"""
from __future__ import annotations

import argparse
import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from astra.crazyflie_link import LineAssembler, send_line
from astra.protocol import CRTP_APP_PORT, CMD_SCAN, ProtocolError, parse_scan_response


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan for nearby BLE beacons via the ASTRA Crazyflie firmware."
    )
    parser.add_argument(
        "--uri",
        default="radio://0/80/2M/E7E7E7E7E7",
        help="Crazyradio URI (default: radio://0/80/2M/E7E7E7E7E7)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=CRTP_APP_PORT,
        help=f"CRTP app port (default: 0x{CRTP_APP_PORT:02X})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cflib.crtp.init_drivers(enable_debug_driver=False)

    print(f"Connecting to {args.uri} …")

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print("Connected. Scanning for BLE beacons — Ctrl-C to stop.\n")

        def on_line(text: str) -> None:
            try:
                result = parse_scan_response(text)
            except ProtocolError as exc:
                print(f"[warning] {exc}")
                # Still re-trigger so the loop keeps running
                send_line(scf.cf, args.port, CMD_SCAN)
                return

            if result.devices:
                print(f"Found {len(result.devices)} device(s):")
                for addr in result.devices:
                    print(f"  {addr}")
            else:
                print("No devices found.")

            print()
            # Re-trigger the scan automatically
            send_line(scf.cf, args.port, CMD_SCAN)

        assembler = LineAssembler(on_line)
        scf.cf.add_port_callback(args.port, assembler.feed)

        # Kick off the first scan
        send_line(scf.cf, args.port, CMD_SCAN)

        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            scf.cf.remove_port_callback(args.port, assembler.feed)
            print("\nScan stopped.")


if __name__ == "__main__":
    main()