#!/usr/bin/env python3
"""
receive_appchannel.py — Print ASTRA telemetry samples in real time.

Two modes of operation:

  (default)   Full telemetry: binds to the beacon and reads drone position
              (x, y, yaw) from the Crazyflie state estimator via the cflib
              log framework.  Each combined sample is printed as it arrives.
              Requires the drone to be flying with the state estimator active.

  --raw       Lightweight RSSI-only mode: binds to the beacon and polls
              DISTANCE directly over CRTP, without starting the log framework.
              Useful for bench testing beacon connectivity before a flight,
              when no position data is needed.

Usage:
    python scripts/receive_appchannel.py \\
        --uri radio://0/80/2M/E7E7E7E7E7 \\
        --beacon AA:BB:CC:DD:EE:FF

    python scripts/receive_appchannel.py \\
        --uri radio://0/80/2M/E7E7E7E7E7 \\
        --beacon AA:BB:CC:DD:EE:FF \\
        --raw
"""
from __future__ import annotations

import argparse
import time

import threading

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from astra.crazyflie_link import AstraLink, LineAssembler, send_line
from astra.protocol import (
    CRTP_APP_PORT,
    CMD_DISTANCE,
    Telemetry,
    cmd_bind,
)
from astra.rssi import rssi_to_distance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive and print ASTRA telemetry from a Crazyflie in real time."
    )
    parser.add_argument(
        "--uri",
        default="radio://0/80/2M/E7E7E7E7E7",
        help="Crazyradio URI (default: radio://0/80/2M/E7E7E7E7E7)",
    )
    parser.add_argument(
        "--beacon",
        required=True,
        help="BLE beacon address to bind to (e.g. AA:BB:CC:DD:EE:FF)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="DISTANCE polling interval in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="RSSI-only mode: skip position tracking, no log framework required",
    )
    return parser.parse_args()


def run_full(args: argparse.Namespace) -> None:
    """Full telemetry mode: position from log framework + RSSI from DISTANCE."""
    link = AstraLink(uri=args.uri, beacon_addr=args.beacon, poll_interval=args.interval)

    def on_telemetry(t: Telemetry) -> None:
        print(f"x={t.x:.3f}  y={t.y:.3f}  yaw={t.yaw:.3f}  rssi={t.rssi:4d} dBm")

    print(f"Connecting to {args.uri}")
    print(f"Binding to beacon {args.beacon}")
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


def run_raw(args: argparse.Namespace) -> None:
    """Raw RSSI-only mode: direct CRTP, no log framework, no position data."""
    cflib.crtp.init_drivers(enable_debug_driver=False)

    print(f"Connecting to {args.uri} (raw mode)")
    print(f"Binding to beacon {args.beacon}")

    import json as _json  # noqa: PLC0415

    bind_ack = threading.Event()

    def on_line(text: str) -> None:
        try:
            data = _json.loads(text)
        except _json.JSONDecodeError:
            print(f"[warning] malformed JSON: {text!r}")
            return

        result = data.get("result")

        if isinstance(result, str):
            # BIND acknowledgement
            bind_ack.set()
        elif result is not None:
            try:
                rssi = int(result)
            except (TypeError, ValueError):
                print(f"[warning] non-integer RSSI: {result!r}")
                return
            distance = rssi_to_distance(rssi)
            print(f"rssi={rssi:4d} dBm  →  distance={distance:.2f} m")
        else:
            print(f"[warning] unexpected response: {text!r}")

    assembler = LineAssembler(on_line)

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        scf.cf.add_port_callback(CRTP_APP_PORT, assembler.feed)

        bind_ack.clear()
        send_line(scf.cf, CRTP_APP_PORT, cmd_bind(args.beacon))
        if not bind_ack.wait(timeout=5.0):
            scf.cf.remove_port_callback(CRTP_APP_PORT, assembler.feed)
            raise RuntimeError(
                f"BIND timed out: no acknowledgement from firmware "
                f"for beacon {args.beacon!r}"
            )

        try:
            while True:
                send_line(scf.cf, CRTP_APP_PORT, CMD_DISTANCE)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            scf.cf.remove_port_callback(CRTP_APP_PORT, assembler.feed)
            print("\nStopped.")


def main() -> None:
    args = parse_args()
    if args.raw:
        run_raw(args)
    else:
        run_full(args)


if __name__ == "__main__":
    main()