#!/usr/bin/env python3
"""
console.py — Interactive free-text CRTP terminal for the ASTRA Crazyflie firmware.

Connects to the Crazyflie and opens a bidirectional text channel over CRTP
port 0x0E.  Every line you type is sent to the firmware as a UTF-8 command;
every line the firmware sends back is printed above the prompt.
Firmware DEBUG_PRINT output (CRTP port 0) is forwarded with a [CF] prefix.

This is a raw debugging tool — no beacon binding, no RSSI processing.
For beacon scanning use scan.py, for RSSI monitoring use receive_appchannel.py.

Usage:
    python scripts/console.py
    python scripts/console.py --uri radio://0/80/2M/E7E7E7E7E7
    python scripts/console.py --uri radio://0/80/2M/E7E7E7E7E7 --port 0x0E
"""

import argparse
import time

import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from astra.console import Console
from astra.crazyflie_link import FirmwareLogAssembler, LineAssembler, send_line
from astra.protocol import CRTP_APP_PORT


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive free-text CRTP terminal for the ASTRA Crazyflie firmware."
    )
    parser.add_argument(
        "--uri",
        type=str,
        default="radio://0/40/2M/E7E7E7E7E6",
        help="Crazyradio URI",
    )
    parser.add_argument(
        "--port",
        type=lambda x: int(x, 0),
        default=CRTP_APP_PORT,
        help="CRTP port to use (default: 0x0E)",
    )
    args = parser.parse_args()

    cflib.crtp.init_drivers()

    print(f"Connecting to Crazyflie at {args.uri} …")

    console = Console()

    def on_line(text: str) -> None:
        console.log(text)

    assembler = LineAssembler(on_line)

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print("Connected. Type a line and press Enter to send. Ctrl-C to quit.\n")

        # Forward firmware DEBUG_PRINT output (CRTP port 0) to the console
        def on_firmware_log(text: str) -> None:
            console.log(f"[CF] {text}")

        fw_assembler = FirmwareLogAssembler(on_firmware_log)
        scf.cf.console.receivedChar.add_callback(fw_assembler.feed)

        scf.cf.add_port_callback(args.port, assembler.feed)

        def console_handler(user_input: str) -> None:
            if user_input:
                send_line(scf.cf, args.port, user_input)

        console.callback = console_handler
        console.start()

        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            console.stop()
            scf.cf.remove_port_callback(args.port, assembler.feed)
            scf.cf.console.receivedChar.remove_callback(fw_assembler.feed)
            print("\nClosing link.")


if __name__ == "__main__":
    main()