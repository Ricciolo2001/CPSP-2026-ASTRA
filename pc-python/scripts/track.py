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
from typing import Literal, Optional

import astra.console
import cflib
import cflib.crtp
from astra.crazyflie import check_crazyradio, get_bound_mac, set_bound_mac
from astra.localization import trilaterate_lm, trilaterate_lstsq
from astra.rssi import MedianEmaFilter, rssi_to_distance
from cflib.crazyflie import Crazyflie, namedtuple
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.syncLogger import SyncLogger

DEFAULT_TX_POWER = -40.0  # dBm at 1 m
DEFAULT_PATH_LOSS_N = 2.0  # Free-space path loss exponent

DEFAULT_ALPHA = 0.15  # EMA smoothing factor
DEFAULT_SAMPLE_NUM = 50  # Number of samples to keep for median filtering
DEFAULT_SAMPLE_INTERVAL_MS = 100  # Log sampling interval in milliseconds

# The height of the beacon above the ground plane. This is used to improve
# distance estimation by accounting for the vertical offset in the trilateration.
Z_BEACON = 0.2


logger = logging.getLogger(__name__)


@dataclass
class GuiRecord:
    type: str
    x: float
    y: float


Measurement = namedtuple("Measurement", ["timestamp", "x", "y", "distance", "rssi"])

INITIAL_POSITIONS = [
    (1.0, 0.0),
    (1.0, 1.0),
    (0.0, 1.0),
    (0.0, 0.0),
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

        logger.debug(f"Estimating position with {len(self.measurements)} measurements:")
        for m in self.measurements:
            logger.debug(
                f"  - t={m.timestamp:.2f} s"
                f", x={m.x:.2f} m, y={m.y:.2f} m"
                f", d={m.distance:.2f} m, rssi={m.rssi:.2f} dBm"
            )

        # Estimator 1: Trilaterazione lineare
        tril = trilaterate_lstsq(
            anchors=[(m.x, m.y) for m in self.measurements],
            distances=[m.distance for m in self.measurements],
        )
        logger.info(
            f"  [trilateration] x={tril.x:.3f} y={tril.y:.3f} total_error={tril.rmse:.3f}"
        )
        if tril.rmse > 1.0:
            logger.warning(
                "  [trilateration] high total error, estimate may be unreliable"
            )

        # Estimator 2: Gauss-Newton iterativo

        # Consider the best measurement as the one with the strongest RSSI
        best = max(self.measurements, key=lambda m: m.rssi)

        # Higher RSSI -> more weight
        max_weight = 1000
        weights = [
            min(1.0 / ((m.distance + 1e-3) ** 2), max_weight) for m in self.measurements
        ]

        est = trilaterate_lm(
            anchors=[(m.x, m.y) for m in self.measurements],
            distances=[m.distance for m in self.measurements],
            initial_guess=(best.x, best.y),
            weights=weights,
        )
        logger.info(
            f"  [Gauss-Newton] x={est.x:.3f} y={est.y:.3f} rmse={est.rmse:.3f} "
            f"samples_used={est.samples_used} converged={est.converged}"
        )

        if not est.converged:
            logger.warning(
                "  [Gauss-Newton] did not converge, consider tuning parameters"
            )

        return est.x, est.y

    def positions(self):
        n = len(self.measurements)

        # Yield initial positions first
        while n < len(INITIAL_POSITIONS):
            yield INITIAL_POSITIONS[n]
            n += 1

        # Then keep yielding estimates
        while True:
            yield self.estimate()

    def track(self, measurement: Measurement):
        self.measurements.append(measurement)


class GUI:
    def __init__(self, tracker: BeaconTracker, gui_queue: queue.Queue):
        self.tracker = tracker
        self.gui_queue = gui_queue
        self.root = tk.Tk()
        self.root.title("ASTRA Beacon Tracker")

        # Canvas Setup (1 meter = 100 pixels)
        self.scale = 100
        self.offset = 500  # Center of a 1000x1000 canvas
        self.canvas = tk.Canvas(self.root, width=1000, height=1000, bg="#f0f0f0")
        self.canvas.pack(padx=10, pady=10)

        # Draw Grid
        self.canvas.create_line(0, self.offset, 1000, self.offset, fill="#ddd")
        self.canvas.create_line(self.offset, 0, self.offset, 1000, fill="#ddd")

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

    gui_queue: queue.Queue[GuiRecord]
    start_thread: threading.Thread
    estimator: Literal["linear", "gauss"]

    def __init__(
        self,
        scf: SyncCrazyflie,
        gui_queue: queue.Queue[GuiRecord],
        estimator: Literal["linear", "gauss"] = "linear",
    ):
        self.scf = scf
        self.gui_queue = gui_queue
        self.tracker = BeaconTracker(scf)
        self.should_exit = threading.Event()
        self.estimator = estimator

    def stop(self, timeout: float = 5.0):
        t = getattr(self, "start_thread", None)
        if t is None:
            return
        if not t.is_alive():
            return

        self.should_exit.set()
        t.join(timeout=timeout)
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
        logger.info("[mission] resetting Kalman estimator...")
        self.scf.cf.param.set_value("kalman.resetEstimation", "1")
        time.sleep(2.0)

        HEIGHT = 1.0

        logger.info(f"[mission] takeoff → {HEIGHT:.2f} m")
        self.scf.cf.high_level_commander.takeoff(HEIGHT, 2.0)
        self._wait(3.0)  # wait for takeoff to complete

        sampling_duration = args.sample_interval * args.sample_num / 1000.0
        logger.info(
            f"[mission] sampling duration per point: {sampling_duration:.2f} s "
            f"(interval={args.sample_interval} ms, num={args.sample_num})"
        )

        last_pos = (0.0, 0.0, 0.0)

        try:
            for target_x, target_y in self.tracker.positions():
                if self.should_exit.is_set():
                    logger.info("[mission] should_exit set, aborting mission loop")
                    break

                target_x, target_y = self._clamp_target(
                    src=(last_pos[0], last_pos[1]),
                    dst=(target_x, target_y),
                    max_dist=1.5,
                )

                logger.info(
                    f"[mission] Flying to target ({target_x:.2f}, {target_y:.2f})..."
                )
                self.gui_queue.put(GuiRecord(type="target", x=target_x, y=target_y))

                # Pass the queue into the flight function
                last_pos = self._move_to_pos((target_x, target_y, HEIGHT))
                self._wait(1.0)  # stabilize for a moment at the target

                logger.info("[mission] Sampling RSSI...")

                try:
                    rssi = self._sample_rssi(duration=sampling_duration)
                except Exception as e:
                    logger.error(f"Error during RSSI sampling: {e}", exc_info=True)
                    return

                distance_3d = rssi_to_distance(rssi, args.tx_power, args.path_loss)

                drone_z = last_pos[2]
                delta_z = drone_z - Z_BEACON

                if distance_3d > delta_z:
                    distance_2d = math.sqrt(distance_3d**2 - delta_z**2)
                else:
                    distance_2d = 0.01

                logger.info(
                    f"  RSSI={rssi:.2f} dBm"
                    f" → distance_3d={distance_3d:.2f} m"
                    f" → distance_2d={distance_2d:.2f} m (delta_z={delta_z:.2f} m)"
                )

                # Update tracker with the new measurement
                self.tracker.track(
                    Measurement(time.time(), target_x, target_y, distance_2d, rssi)
                )

        except Exception as e:
            logger.error(f"Mission Error: {e}", exc_info=True)
        finally:
            self.scf.cf.high_level_commander.land(0.0, 2.0)

        logger.info("[mission] done.")

    def _clamp_target(
        self, src: tuple[float, float], dst: tuple[float, float], max_dist: float
    ):
        """Clamp the target position to be within max_dist from the source."""
        dx = dst[0] - src[0]
        dy = dst[1] - src[1]
        dist = math.sqrt(dx**2 + dy**2)
        if dist > max_dist:
            scale = max_dist / dist
            new_x = src[0] + dx * scale
            new_y = src[1] + dy * scale
            logger.warning(
                f"Target ({dst[0]:.2f}, {dst[1]:.2f}) is {dist:.2f} m away, which exceeds the max of {max_dist:.2f} m. "
                f"Clamping to ({new_x:.2f}, {new_y:.2f})."
            )
            return new_x, new_y
        else:
            return dst

    def _move_to_pos(
        self,
        target: tuple[float, float, float],
        arrival_radius: float = 0.15,
    ):
        log_period_ms = 500  # log to console every 0.5 seconds

        # Listen to postion estimates
        log_conf = LogConfig(name="move_to_pos", period_in_ms=50)
        log_conf.add_variable("stateEstimate.x", "float")  # 4 bytes
        log_conf.add_variable("stateEstimate.y", "float")  # 4 bytes
        log_conf.add_variable("stateEstimate.z", "float")  # 4 bytes
        log_conf.add_variable("pm.batteryLevel", "uint8_t")  # 2 bytes
        # total = 14

        last_pos = None

        with SyncLogger(self.scf.cf, log_conf) as cf_logger:
            logger.info(
                f"[move_to_pos] go_to ({target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f})"
            )
            self.scf.cf.high_level_commander.go_to(
                target[0], target[1], target[2], 0, 1.0
            )

            last_time = 0

            for ts_ms, data, _ in cf_logger:
                if self.should_exit.is_set():
                    logger.info(
                        "[move_to_pos] should_exit set, breaking position log loop"
                    )
                    break

                x = data["stateEstimate.x"]
                y = data["stateEstimate.y"]
                z = data["stateEstimate.z"]
                bat = data["pm.batteryLevel"]

                last_pos = (x, y, z)

                self.gui_queue.put(GuiRecord(type="pos", x=x, y=y))

                dist_2d = math.sqrt((x - target[0]) ** 2 + (y - target[1]) ** 2)

                if dist_2d <= arrival_radius:
                    logger.info(f"  [pos cb] arrived at target! dist={dist_2d:.3f} m")
                    self.gui_queue.put(
                        GuiRecord(type="acquired", x=target[0], y=target[1])
                    )
                    break

                if last_time == 0.0:
                    last_time = ts_ms
                elif (ts_ms - last_time) >= log_period_ms:
                    last_time = ts_ms
                    logger.debug(
                        f"  [pos cb] dist={dist_2d:.3f} m"
                        f"\t t={ts_ms:.2f} s"
                        f"\t pos=({x:.3f}, {y:.3f}, {z:.3f})"
                        f"\t dest=({target[0]:.3f}, {target[1]:.3f}, {target[2]:.3f})"
                        f"\t bat={bat:.1f}%"
                    )

        logger.info(
            "[move_to_pos] arrived at "
            f"({target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f})"
        )
        return last_pos

    def _sample_rssi(self, duration: float) -> float:
        cf = self.scf.cf

        rssi_filter = MedianEmaFilter(
            window_size=DEFAULT_SAMPLE_NUM, alpha=DEFAULT_ALPHA
        )

        start_time = time.time()
        last_time = 0
        log_period_ms = 1000  # log every 1 second

        logconf = LogConfig(name="rssi_sample", period_in_ms=DEFAULT_SAMPLE_INTERVAL_MS)
        logconf.add_variable("astra.bound_device_rssi", "int32_t")  # 4 bytes

        with SyncLogger(cf, logconf) as cf_logger:
            for ts, data, _ in cf_logger:
                if self.should_exit.is_set():
                    logger.warning(
                        "[_sample_rssi] should_exit set, breaking RSSI log loop"
                    )
                    break
                elif (time.time() - start_time) >= duration:
                    logger.debug(
                        f"[_sample_rssi] sampling duration of {duration:.2f} s reached"
                    )
                    break

                rssi = data["astra.bound_device_rssi"]
                rssi_filter.update(rssi)

                if last_time != 0 and (ts - last_time) >= log_period_ms:
                    logger.info(
                        f"[rssi] t={ts:.2f} s\t RSSI={rssi} dBm\t filtered={rssi_filter.value:.2f} dBm"
                    )
                last_time = ts

        return rssi_filter.value

    def _wait(self, duration: float):
        """Wait for the specified duration or until should_exit is set."""
        self.should_exit.wait(timeout=duration)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "BLE_MAC",
        help="BLE MAC address of the beacon to track (e.g. AA:BB:CC:DD:EE:FF)",
    )

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
        "--path-loss",
        type=float,
        default=2.0,
        help="Path-loss exponent for the log-distance model (default: 2.0, free-space)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (default: False)",
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

    logging_level = logging.DEBUG if args.verbose else logging.INFO
    astra.console.basic_config(level=logging_level)
    # logging.getLogger("cflib").setLevel(logging.ERROR)

    logger.debug("Initializing Crazyflie drivers...")
    cflib.crtp.init_drivers()

    if not check_crazyradio():
        logger.error(
            "Crazyradio not found or failed to initialize."
            " Run with --verbose for details."
        )
        sys.exit(1)

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        logger.info(f"Connected to {args.uri}")

        # Print firmware DEBUG_PRINT messages directly to console
        fw_log = astra.console.LineBuffer(lambda line: logger.debug(f"[CF]: {line}"))
        scf.cf.console.receivedChar.add_callback(fw_log.feed)

        # Use Kalman estimator
        scf.cf.param.set_value("stabilizer.estimator", "2")

        # Set up BLE MAC binding
        logger.info(f"Setting bound device MAC → {args.BLE_MAC}")
        set_bound_mac(scf, args.BLE_MAC)
        time.sleep(0.2)  # allow the firmware callback to run

        current_mac = get_bound_mac(scf)
        logger.info(f"Bound device MAC: {current_mac}")

        gui_queue: queue.Queue[GuiRecord] = queue.Queue()
        mission = AstraController(scf, gui_queue)

        # Start mission in a separate thread
        mission.start(args)

        gui = GUI(mission.tracker, gui_queue)

        try:
            gui.run()  # tk must run in the main thread
        except KeyboardInterrupt:
            logger.info("\n[main] Ctrl+C received, stopping...")
        finally:
            mission.stop()
            logger.info("[main] mission stopped, landing and exiting...")
            scf.cf.high_level_commander.land(0.0, 2.0)
            time.sleep(2.5)

    exit(0)


if __name__ == "__main__":
    main()
