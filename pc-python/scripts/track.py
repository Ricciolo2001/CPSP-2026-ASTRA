# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

# Flow:
# 1. Connettersi al CF
# 2. Impostare il MAC address del BLE
# 3. Armare il CF
# 4. Loop:
#   - "Crea un punto"
#   - Imposta setpoint sul CF a quel punto
#   - Attendi che il CF raggiunga il setpoint
#   - Campiona il RSSI e la distanza stimata per tot secondi

import argparse
import collections
import logging
import math
import queue
import sys
import threading
import time
import tkinter as tk
import warnings
from dataclasses import dataclass
from typing import Optional

import cflib
import cflib.crtp
from astra.crazyflie import LineBuffer, get_bound_mac, set_bound_mac
from astra.localization import trilaterate2d
from astra.rssi import MedianEmaFilter, rssi_to_distance
from cflib.crazyflie import Crazyflie, namedtuple
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

DEFAULT_TX_POWER = -40.0  # dBm at 1 m
DEFAULT_PATH_LOSS_N = 2.0  # Free-space path loss exponent

DEFAULT_ALPHA = 0.15  # EMA smoothing factor
DEFAULT_SAMPLE_NUM = 30  # Number of samples to keep for median filtering
DEFAULT_SAMPLE_INTERVAL_MS = 100  # Log sampling interval in milliseconds


@dataclass
class GuiRecord:
    type: str
    x: float
    y: float


Measurement = namedtuple("Measurement", ["timestamp", "x", "y", "distance"])

INITIAL_POSITIONS = [
    (0.0, 0.0),
    (1.0, 0.0),
    (0.0, 1.0),
]


class BeaconTracker:
    initial_positions: list[tuple[float, float]]
    measurements: collections.deque[Measurement]

    def __init__(
        self,
        scf: SyncCrazyflie,
        keep: int = 6,
        initial_positions: Optional[list[tuple[float, float]]] = None,
    ):
        self.scf = scf
        self.measurements = collections.deque(maxlen=keep)
        self.initial_positions = initial_positions or INITIAL_POSITIONS

    def estimate(self) -> tuple[float, float]:

        targ, res, l2 = trilaterate2d(
            [(m.x, m.y) for m in self.measurements],
            [m.distance for m in self.measurements],
        )

        print(f"  [trilaterate2d] target={targ} residuals={res} l2={l2:.3f}")
        return targ

    def positions(self):
        n = len(self.measurements)

        # Yield initial positions first
        while n < len(INITIAL_POSITIONS):
            yield INITIAL_POSITIONS[n]
            n += 1

        # Then keep yielding estimates
        while True:
            next_pos = self.estimate()
            if next_pos is None:
                raise RuntimeError("Unexpected empty measurements in positions()")
            yield next_pos

    def track(self, measurement: Measurement):
        self.measurements.append(measurement)


class GUI:
    def __init__(
        self, tracker: BeaconTracker, gui_queue: queue.Queue, triangle_side: float = 0.6
    ):
        self.tracker = tracker
        self.gui_queue = gui_queue
        self.root = tk.Tk()
        self.root.title("ASTRA Beacon Tracker")

        self.triangle_side = triangle_side

        # Canvas Setup (1 meter = 100 pixels)
        self.scale = 100
        self.offset = 250  # Center of a 500x500 canvas
        self.canvas = tk.Canvas(self.root, width=500, height=500, bg="#f0f0f0")
        self.canvas.pack(padx=10, pady=10)

        # Draw Grid
        self.canvas.create_line(0, self.offset, 500, self.offset, fill="#ddd")
        self.canvas.create_line(self.offset, 0, self.offset, 500, fill="#ddd")

        # UI Elements
        self.drone_marker = self.canvas.create_oval(
            0, 0, 0, 0, fill="red", outline="white"
        )
        self.target_marker = self.canvas.create_oval(
            0, 0, 0, 0, fill="blue", outline=""
        )
        self.status_label = tk.Label(
            self.root, text="Status: Waiting for connection...", font=("Consolas", 10)
        )
        self.status_label.pack()

    def _to_coords(self, x, y):
        """Convert meters to pixels."""
        cx = self.offset + (x * self.scale)
        cy = self.offset - (y * self.scale)  # Flip Y for screen space
        return cx, cy

    def update_loop(self):
        try:
            while True:
                record = self.gui_queue.get_nowait()
                cx, cy = self._to_coords(record.x, record.y)

                if record.type == "target":
                    # Update/Show blue target circle
                    self.canvas.coords(
                        self.target_marker, cx - 10, cy - 10, cx + 10, cy + 10
                    )

                elif record.type == "acquired":
                    # Mark as acquired with a green square
                    self.canvas.create_rectangle(
                        cx - 6, cy - 6, cx + 6, cy + 6, fill="#2ecc71", outline="white"
                    )

                elif record.type == "pos":
                    # Update Drone Position (Red Dot)
                    self.canvas.coords(
                        self.drone_marker, cx - 8, cy - 8, cx + 8, cy + 8
                    )
                    # Breadcrumb (Gray)
                    self.canvas.create_oval(
                        cx - 1, cy - 1, cx + 1, cy + 1, fill="#bdc3c7", outline=""
                    )
                    self.status_label.config(
                        text=f"X: {record.x:.2f} Y: {record.y:.2f}"
                    )
        except queue.Empty:
            pass
        self.root.after(50, self.update_loop)

    def run(self):
        self.update_loop()
        self.root.mainloop()


class AstraController:
    scf: SyncCrazyflie

    should_exit: threading.Event
    tracker: BeaconTracker

    queue: queue.Queue[GuiRecord]
    start_thread: threading.Thread

    def __init__(self, scf: SyncCrazyflie, queue: queue.Queue[GuiRecord]):
        self.scf = scf
        self.gui_queue = queue
        self.tracker = BeaconTracker(scf)
        self.should_exit = threading.Event()

    def stop(self):
        t = self.start_thread
        if t is None or not t.is_alive():
            raise RuntimeError("Mission not started or already stopped.")

        self.should_exit.set()
        t.join(timeout=5.0)
        if t.is_alive():
            warnings.warn("Mission thread did not exit in time.")

        self.should_exit.clear()

    def start(self, args: argparse.Namespace):
        self.should_exit.clear()
        self.start_thread = threading.Thread(target=self._start, args=(args,))
        self.start_thread.start()

    def _start(self, args: argparse.Namespace):
        """The actual flight sequence."""

        # Reset the Kalman estimator
        print("[mission] resetting Kalman estimator...")
        self.scf.cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(2.0)

        HEIGHT = 0.5

        print(f"[mission] takeoff → {HEIGHT:.2f} m")
        self.scf.cf.high_level_commander.takeoff(HEIGHT, 2.0)
        self._wait(3.0)  # wait for takeoff to complete

        try:
            for target_x, target_y in self.tracker.positions():
                if self.should_exit.is_set():
                    print("[mission] should_exit set, aborting mission loop")
                    break

                print(f"[mission] Flying to target ({target_x:.2f}, {target_y:.2f})...")
                self.gui_queue.put(GuiRecord(type="target", x=target_x, y=target_y))

                # Pass the queue into the flight function
                self._move_to_pos((target_x, target_y, 0.5))

                print("[mission] Sampling RSSI...")
                rssi = self._sample_rssi(duration=5.0)

                distance = rssi_to_distance(rssi, args.tx_power, args.path_loss_n)
                print(f"[mission] Estimated distance: {distance:.2f} m")

                # Update tracker with the new measurement
                self.tracker.track(
                    Measurement(time.time(), target_x, target_y, distance)
                )

        except Exception as e:
            print(f"Mission Error: {e}")
        finally:
            self.scf.cf.high_level_commander.land(0.0, 2.0)

        print("[mission] done.")

    def _move_to_pos(
        self,
        target: tuple[float, float, float],
        arrival_radius: float = 0.15,
    ):
        cf = self.scf.cf

        sem = threading.Semaphore(0)

        last_time = 0
        log_period_ms = 500  # log every 500 ms

        def _on_pos(ts_ms: int, data: dict[str, float], _):
            nonlocal last_time
            x = data["stateEstimate.x"]
            y = data["stateEstimate.y"]
            z = data["stateEstimate.z"]
            bat = data["pm.batteryLevel"]

            self.gui_queue.put(GuiRecord(type="pos", x=x, y=y))

            dist = math.sqrt((x - target[0]) ** 2 + (y - target[1]) ** 2)

            if dist <= arrival_radius:
                print(f"  [pos cb] entro in area di arrivo (dist={dist:.3f} m)")
                sem.release()

            if last_time == 0.0:
                last_time = ts_ms
            elif ts_ms - last_time < log_period_ms:
                return
            last_time = ts_ms

            print(
                f"  [pos cb] dist={dist:.3f} m"
                f"\t t={ts_ms:.2f} s"
                f"\t pos=({x:.3f}, {y:.3f}, {z:.3f})"
                f"\t dest=({target[0]:.3f}, {target[1]:.3f}, {target[2]:.3f})"
                f"\t bat={bat:.1f}%"
            )

        # Listen to postion estimates
        logconf = LogConfig(name="move_to_pos", period_in_ms=50)
        logconf.add_variable("stateEstimate.x", "float")  # 4 bytes
        logconf.add_variable("stateEstimate.y", "float")  # 4 bytes
        logconf.add_variable("stateEstimate.z", "float")  # 4 bytes
        logconf.add_variable("pm.batteryLevel", "uint8_t")  # 2 bytes
        # total = 14

        cf.log.add_config(logconf)
        logconf.data_received_cb.add_callback(_on_pos)

        try:
            logconf.start()

            # --- go_to ---
            print(
                f"[move_to_pos] go_to ({target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f})"
            )
            cf.high_level_commander.go_to(target[0], target[1], target[2], 0, 0.3)

            # wait until we enter the arrival radius
            while not self.should_exit.is_set():
                if sem.acquire(timeout=0.1):
                    print(
                        "[move_to_pos] arrived at "
                        f"({target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f})"
                    )
                    break
        finally:
            logconf.stop()

    def _sample_rssi(self, duration: float) -> float:
        cf = self.scf.cf

        logconf = LogConfig(name="rssi_sample", period_in_ms=DEFAULT_SAMPLE_INTERVAL_MS)
        logconf.add_variable("astra.bound_device_rssi", "int32_t")  # 4 bytes
        cf.log.add_config(logconf)

        filter = MedianEmaFilter(window_size=DEFAULT_SAMPLE_NUM, alpha=DEFAULT_ALPHA)

        last_time = 0

        def _on_rssi(ts, data, _):
            rssi = data["astra.bound_device_rssi"]
            filter.update(rssi)

            nonlocal last_time
            if last_time == 0.0:
                last_time = ts
            elif ts - last_time < 1000:  # log every 1 second
                return
            last_time = ts

            print(
                f"[log] t={ts:.2f} s\t RSSI={rssi} dBm\t filtered={filter.value:.2f} dBm"
            )

        logconf.data_received_cb.add_callback(_on_rssi)

        try:
            logconf.start()
            print(f"[sample_rssi] sampling for {duration:.2f} seconds...")
            time.sleep(duration)
        finally:
            logconf.stop()

        return filter.value

    def _wait(self, duration: float):
        """Wait for the specified duration or until should_exit is set."""
        start_time = time.time()
        while not self.should_exit.is_set():
            elapsed = time.time() - start_time
            if elapsed >= duration:
                break
            time.sleep(0.1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--uri",
        default="radio://0/83/2M/E7E7E7E7EA",
        help="Crazyflie radio URI (default: radio://0/83/2M/E7E7E7E7EA)",
    )
    parser.add_argument(
        "--tx-power",
        type=float,
        default=DEFAULT_TX_POWER,
        help=f"Beacon TX power at 1 m in dBm used by the log-distance model (default: {DEFAULT_TX_POWER})",
    )
    parser.add_argument(
        "--path-loss-n",
        type=float,
        default=2.0,
        help="Path-loss exponent n for the log-distance model (default: 2.0, free-space)",
    )
    parser.add_argument(
        "--mac",
        default=None,
        metavar="AA:BB:CC:DD:EE:FF",
        help="BLE MAC address to bind before starting (use 00:00:00:00:00:00 to unbind). "
        "If omitted, the current bound device is used.",
    )
    parser.add_argument(
        "--triangle-side",
        type=float,
        default=0.6,
        help="Triangle side length in metres for manual guide overlay (default: 0.6)",
    )
    parser.add_argument(
        "--fw-log",
        action="store_true",
        help="Print firmware DEBUG_PRINT messages directly to console",
    )
    parser.add_argument(
        "--sample-interval",
        type=int,
        default=DEFAULT_SAMPLE_INTERVAL_MS,
        help=f"Log sampling interval in milliseconds (default: {DEFAULT_SAMPLE_INTERVAL_MS})",
    )
    parser.add_argument(
        "--sample-num",
        type=int,
        default=DEFAULT_SAMPLE_NUM,
        help=f"Number of samples to keep for median filtering (default: {DEFAULT_SAMPLE_NUM})",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help=f"EMA smoothing factor alpha in (0, 1] (default: {DEFAULT_ALPHA})",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.mac is None:
        print("No --mac specified; unable to proceed", file=sys.stderr)
        return

    logging.basicConfig(level=logging.WARN)
    cflib.crtp.init_drivers()

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print(f"Connected to {args.uri}")

        # Print firmware DEBUG_PRINT messages directly to console
        if args.fw_log:
            fw_log = LineBuffer(lambda line: print(f"[CF] {line}", flush=True))
            scf.cf.console.receivedChar.add_callback(fw_log.feed)

        # Use Kalman estimator
        scf.cf.param.set_value("stabilizer.estimator", "2")

        # Set up BLE MAC binding
        if args.mac is not None:
            print(f"Setting bound device MAC → {args.mac}")
            set_bound_mac(scf, args.mac)
            time.sleep(0.2)  # allow the firmware callback to run

        current_mac = get_bound_mac(scf)
        if current_mac == "00:00:00:00:00:00":
            print("Bound device: (none — unbound)")
        else:
            print(f"Bound device MAC: {current_mac}")

        gui_queue: queue.Queue[GuiRecord] = queue.Queue()
        mission = AstraController(scf, gui_queue)

        # Start mission in a separate thread
        mission.start(args)

        gui = GUI(mission.tracker, gui_queue, triangle_side=args.triangle_side)

        try:
            gui.run()  # tk must run in the main thread
        except KeyboardInterrupt:
            print("\n[main] Ctrl+C received, stopping...")
        finally:
            mission.stop()
            print("[main] mission stopped, landing and exiting...")
            scf.cf.high_level_commander.land(0.0, 2.0)
            time.sleep(2.5)

        exit(0)


if __name__ == "__main__":
    main()
