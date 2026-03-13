import json
import sys
import threading
import time

import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crtp.crtpstack import CRTPPacket

# CRTP packets carry at most 30 bytes of payload
CRTP_MAX_PAYLOAD = 30


# ---------------------------------------------------------------------------
# Console helper – interleaves received lines with a persistent "> " prompt
# ---------------------------------------------------------------------------


class Console:
    def __init__(self, callback=None):
        self.callback = callback
        self._lock = threading.Lock()
        self._input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        self._input_thread.start()
        self._show_prompt()

    def stop(self):
        self._running = False

    def log(self, message):
        """Print a received message above the prompt."""
        with self._lock:
            # Clear the current prompt line, print the message, redraw prompt
            sys.stdout.write(f"\r\033[K{message}\n")
            self._show_prompt()
            sys.stdout.flush()

    def _show_prompt(self):
        sys.stdout.write("> ")
        sys.stdout.flush()

    def _input_loop(self):
        while self._running:
            try:
                line = sys.stdin.readline()
                if line:
                    user_input = line.rstrip("\n")
                    if self.callback:
                        self.callback(user_input)

                    with self._lock:
                        self._show_prompt()
            except (EOFError, KeyboardInterrupt):
                break


# ---------------------------------------------------------------------------
# Chunked send
# ---------------------------------------------------------------------------


def send_line(cf: Crazyflie, port: int, line: str) -> None:
    """
    Encode *line* as UTF-8, append a newline terminator, then send it as
    one or more CRTP packets of at most CRTP_MAX_PAYLOAD bytes each.
    """
    data = (line + "\n").encode("utf-8")
    for offset in range(0, len(data), CRTP_MAX_PAYLOAD):
        chunk = data[offset : offset + CRTP_MAX_PAYLOAD]
        pk = CRTPPacket()
        pk.port = port
        pk.channel = 0
        pk.data = chunk
        cf.send_packet(pk)


# ---------------------------------------------------------------------------
# Dechunking receive state
# ---------------------------------------------------------------------------


class LineAssembler:
    """
    Accumulates raw bytes arriving in individual CRTP packets and emits
    complete lines (split on '\\n') via *on_line*.
    """

    def __init__(self, on_line):
        self._buf = bytearray()
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, packet: CRTPPacket) -> None:
        with self._lock:
            self._buf.extend(bytes(packet.data))
            # Emit every complete line that is now in the buffer
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                try:
                    text = line.decode("utf-8")
                except UnicodeDecodeError:
                    text = line.decode("latin-1")
                self._on_line(text)


class FirmwareLogAssembler:
    """
    Receives raw character chunks from cf.console.receivedChar (which fires
    with arbitrary UTF-8 fragments, not full lines) and emits complete lines
    via *on_line*.
    """

    def __init__(self, on_line):
        self._buf = ""
        self._on_line = on_line
        self._lock = threading.Lock()

    def feed(self, text: str) -> None:
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self._on_line(line)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive console for the ASTRA Crazyflie application."
    )
    parser.add_argument("--uri", type=str, default="radio://0/40/2M/E7E7E7E7E6")
    parser.add_argument("--port", type=int, default=0x0E)
    parser.add_argument("--bind", type=str, default=None)
    parser.add_argument(
        "--scan", action="store_true", help="Scan for BLE devices and exit"
    )
    args = parser.parse_args()

    cflib.crtp.init_drivers()

    print(f"Connecting to Crazyflie at {args.uri} …")
    if args.scan:
        print("Scanning for BLE devices …")

        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:

            def trigger_scan():
                send_line(scf.cf, args.port, "SCAN")

            def on_line(text: str) -> None:
                res = json.loads(text)
                if "result" in res and isinstance(res["result"], list):
                    devices = res["result"]
                    print("Received scan result:")
                    for dev in devices:
                        print(f"  - {dev}")
                else:
                    print(f"Received non-result response: {text}")

                # Re-trigger the scan
                send_line(scf.cf, args.port, "SCAN")

            line_assembler = LineAssembler(on_line)
            scf.cf.add_port_callback(args.port, line_assembler.feed)

            send_line(scf.cf, args.port, "SCAN")
            try:
                while True:
                    time.sleep(0.1)
            except KeyboardInterrupt:
                exit(0)

    elif args.bind:
        print(f"Switching to bind mode. Trying to get the distance of {args.bind} …")

        def on_line(text: str) -> None:
            def rssi_to_distance(rssi: int) -> float:
                # Simple path loss model: distance = 10 ^ ((tx_power - rssi) / (10 * n))
                # where tx_power is the RSSI at 1 meter (e.g., -40 dBm) and n is the path loss exponent (e.g., 2 for free space)
                tx_power = -40
                n = 2
                return 10 ** ((tx_power - rssi) / (10 * n))

            res = json.loads(text)
            rssi = res.get("result", None)
            if not rssi:
                print(f"Received non-RSSI response: {text}")
                return
            try:
                rssi = int(rssi)
            except Exception:
                print(f"Received non-integer RSSI: {rssi}")
                return

            distance = rssi_to_distance(rssi)
            print(f"Received RSSI: {rssi} dBm, estimated distance: {distance:.2f} m")

        line_assembler = LineAssembler(on_line)

        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            scf.cf.add_port_callback(args.port, line_assembler.feed)
            send_line(scf.cf, args.port, f"BIND {args.bind}")

            # Then each 500 ms, send a "DISTANCE" command and print the response until the user interrupts with Ctrl-C
            try:
                while True:
                    send_line(scf.cf, args.port, "DISTANCE")
                    time.sleep(0.5)
            except KeyboardInterrupt:
                exit(0)

    else:
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

            # Register the dechunking callback for inbound packets on the app port
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
