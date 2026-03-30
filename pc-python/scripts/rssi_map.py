"""rssi_map.py – Live RSSI gradient map for BLE beacon localisation.

The Crazyflie flies (or is carried) around the room while this script
collects (x, y, RSSI) samples from the ``astra.bound_device_rssi`` log
variable.  A real-time heatmap shows signal strength over the explored
area, and ``astra.localization.estimate_beacon_position`` provides a
running 2-D position estimate for the beacon.

Usage
-----
    python rssi_map.py [--uri radio://...] [--tx-power -59] [--path-loss-n 2.0] [--save-csv out.csv]
"""

from __future__ import annotations

import argparse
import logging
import queue
from collections import deque, namedtuple
from typing import Optional

import numpy as np
import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from astra.rssi import MedianEmaFilter
from astra.localization import estimate_beacon_position, BeaconEstimate
from astra.io import write_csv_rows
from astra.crazyflie_link import FirmwareLogAssembler

try:
    from scipy.interpolate import griddata as _scipy_griddata

    _SCIPY = True
except ImportError:
    _scipy_griddata = None  # type: ignore[assignment]
    _SCIPY = False

# ---------------------------------------------------------------------------
# Shared data container
# ---------------------------------------------------------------------------

DroneData = namedtuple("DroneData", ["x", "y", "yaw", "rssi_raw"])

# Firmware sentinel: astra.c initialises s_bound_device_rssi = -1 when no
# valid RSSI value has been received yet (e.g. right after binding).
_INVALID_RSSI = -1

# ---------------------------------------------------------------------------
# Visualizer
# ---------------------------------------------------------------------------

_HEATMAP_GRID = 200  # interpolation grid resolution (pixels per axis)
_RSSI_VMIN = -100.0  # color-scale lower bound (dBm)
_RSSI_VMAX = -30.0  # color-scale upper bound (dBm)
_RSSI_HISTORY_LEN = 200


class ScalarKalmanFilter:
    """Simple 1D Kalman filter for RSSI smoothing."""

    def __init__(self, process_var: float = 0.5, measurement_var: float = 9.0):
        if process_var <= 0 or measurement_var <= 0:
            raise ValueError("process_var and measurement_var must be > 0")
        self._q = float(process_var)
        self._r = float(measurement_var)
        self._x: Optional[float] = None
        self._p = 1.0

    def update(self, measurement: float) -> float:
        z = float(measurement)
        if self._x is None:
            self._x = z
            return self._x

        # Predict
        p_pred = self._p + self._q
        # Update
        k = p_pred / (p_pred + self._r)
        self._x = self._x + k * (z - self._x)
        self._p = (1.0 - k) * p_pred
        return self._x


class RssiMapVisualizer:
    def __init__(self) -> None:
        plt.ion()
        self.fig = plt.figure(figsize=(11, 6))
        gs = self.fig.add_gridspec(2, 2, width_ratios=[3, 2], height_ratios=[3, 1])

        # ---- left: heatmap ----
        self.ax_map = self.fig.add_subplot(gs[:, 0])
        self.ax_map.set_title("RSSI heatmap")
        self.ax_map.set_xlabel("x (m)")
        self.ax_map.set_ylabel("y (m)")
        self.ax_map.set_aspect("equal", adjustable="datalim")

        # Interpolated background image (created lazily once we have data)
        self._heatmap_img = None

        # Scatter: drone positions coloured by filtered RSSI
        self.scatter = self.ax_map.scatter(
            [], [], c=[], cmap="RdYlGn",
            s=15, zorder=3, vmin=_RSSI_VMIN, vmax=_RSSI_VMAX,
        )
        self.fig.colorbar(
            self.scatter, ax=self.ax_map,
            fraction=0.03, pad=0.02, label="RSSI filtered (dBm)",
        )

        # Trajectory and current position
        (self.traj_line,) = self.ax_map.plot([], [], "b-", lw=0.8, alpha=0.5, zorder=2)
        (self.pose_dot,) = self.ax_map.plot([], [], "bo", ms=7, zorder=4, label="Drone")

        # Guide overlay: triangle waypoints + live manual position marker
        (self.guide_line,) = self.ax_map.plot([], [], "m--", lw=1.2, zorder=6, label="Triangle")
        (self.guide_pts,) = self.ax_map.plot([], [], "ms", ms=6, zorder=7)
        (self.guide_current,) = self.ax_map.plot([], [], "ko", ms=8, zorder=8, label="CF now")
        (self.guide_target,) = self.ax_map.plot([], [], "m*", ms=14, zorder=9, label="Target")
        (self.objective_dot,) = self.ax_map.plot([], [], "gd", ms=10, zorder=10, label="Objective")
        self.objective_xy: Optional[tuple[float, float]] = None

        # Beacon estimate marker (hidden until first estimate)
        (self.beacon_star,) = self.ax_map.plot(
            [], [], "y*", ms=20, zorder=5, label="Beacon est.",
        )
        self.ax_map.legend(loc="upper right", fontsize=9)

        # ---- right-top: RSSI line plot ----
        self.ax_bar = self.fig.add_subplot(gs[0, 1])
        self.ax_bar.set_title("RSSI over time")
        self.ax_bar.set_ylim(_RSSI_VMIN, 0)
        self.ax_bar.set_ylabel("dBm")
        self.ax_bar.set_xlabel("tick")
        self.ax_bar.grid(True, alpha=0.3)
        (self._rssi_line,) = self.ax_bar.plot([], [], "C0-", lw=1.2, label="RSSI")
        (self._rssi_dot,) = self.ax_bar.plot([], [], "ro", ms=4, label="current")
        self.ax_bar.legend(loc="upper right", fontsize=8)
        self._rssi_ticks = deque(maxlen=_RSSI_HISTORY_LEN)
        self._rssi_values = deque(maxlen=_RSSI_HISTORY_LEN)

        # ---- right-bottom: telemetry text ----
        self.ax_info = self.fig.add_subplot(gs[1, 1])
        self.ax_info.axis("off")
        self.txt = self.ax_info.text(
            0, 1, "Waiting for data…", va="top", family="monospace", fontsize=9,
        )
        self.prompt_txt = self.ax_info.text(
            0,
            -0.05,
            "",
            va="top",
            family="monospace",
            fontsize=9,
            color="C3",
            transform=self.ax_info.transAxes,
        )

        plt.tight_layout()
        plt.show(block=False)
        plt.pause(0.1)

    # ------------------------------------------------------------------
    def update(
        self,
        tick: int,
        x: float,
        y: float,
        yaw_rad: float,
        rssi_raw: int,
        rssi_filt: Optional[float],
        xs: list[float],
        ys: list[float],
        rssi_vals: list[float],
        beacon: Optional[BeaconEstimate],
    ) -> None:
        xs_a = np.asarray(xs, dtype=float)
        ys_a = np.asarray(ys, dtype=float)
        rs_a = np.asarray(rssi_vals, dtype=float)

        n = len(xs_a)

        # ---- trajectory & current pose ----
        if n > 0:
            self.traj_line.set_data(xs_a, ys_a)
            self.pose_dot.set_data([x], [y])

            # ---- scatter (always) ----
            self.scatter.set_offsets(np.column_stack([xs_a, ys_a]))
            self.scatter.set_array(rs_a)

            # ---- interpolated heatmap (scipy, ≥ 6 non-collinear samples) ----
            if _SCIPY and _scipy_griddata is not None and n >= 6:
                pad = 0.3
                gx = np.linspace(xs_a.min() - pad, xs_a.max() + pad, _HEATMAP_GRID)
                gy = np.linspace(ys_a.min() - pad, ys_a.max() + pad, _HEATMAP_GRID)
                GX, GY = np.meshgrid(gx, gy)
                try:
                    grid_rssi = _scipy_griddata(
                        np.column_stack([xs_a, ys_a]),
                        rs_a,
                        (GX, GY),
                        method="linear",
                    )
                    extent: tuple[float, float, float, float] = (
                        float(gx[0]), float(gx[-1]), float(gy[0]), float(gy[-1])
                    )
                    if self._heatmap_img is None:
                        self._heatmap_img = self.ax_map.imshow(
                            grid_rssi,
                            extent=extent,
                            origin="lower",
                            cmap="RdYlGn",
                            vmin=_RSSI_VMIN,
                            vmax=_RSSI_VMAX,
                            alpha=0.45,
                            zorder=1,
                            aspect="auto",
                        )
                    else:
                        self._heatmap_img.set_data(grid_rssi)
                        self._heatmap_img.set_extent(extent)
                except Exception:
                    pass  # griddata fails on collinear points; silently ignore

            # ---- beacon estimate marker ----
            if beacon is not None:
                self.beacon_star.set_data([beacon.x], [beacon.y])

            # ---- rescale axes ----
            margin = 0.4
            x_min = float(xs_a.min())
            x_max = float(xs_a.max())
            y_min = float(ys_a.min())
            y_max = float(ys_a.max())
            if self.objective_xy is not None:
                ox, oy = self.objective_xy
                x_min = min(x_min, ox)
                x_max = max(x_max, ox)
                y_min = min(y_min, oy)
                y_max = max(y_max, oy)
            self.ax_map.set_xlim(x_min - margin, x_max + margin)
            self.ax_map.set_ylim(y_min - margin, y_max + margin)

        # ---- RSSI line plot ----
        if rssi_filt is not None:
            self._rssi_ticks.append(tick)
            self._rssi_values.append(rssi_filt)
            ticks = np.asarray(self._rssi_ticks, dtype=float)
            values = np.asarray(self._rssi_values, dtype=float)
            self._rssi_line.set_data(ticks, values)
            self._rssi_dot.set_data([ticks[-1]], [values[-1]])
            self.ax_bar.set_xlim(ticks[0], max(ticks[0] + 1, ticks[-1]))

        # ---- telemetry text ----
        rssi_raw_str = f"{rssi_raw} dBm" if rssi_raw != _INVALID_RSSI else "N/A"
        rssi_filt_str = f"{rssi_filt:.1f} dBm" if rssi_filt is not None else "N/A"
        if beacon is not None:
            beacon_str = (
                f"({beacon.x:.3f}, {beacon.y:.3f}) m\n"
                f"  RMSE={beacon.rmse:.3f} m  n={beacon.samples_used}"
            )
        else:
            need = max(0, 3 - n)
            beacon_str = f"N/A (need {need} more sample{'s' if need != 1 else ''})"

        self.txt.set_text(
            f"Tick:       {tick}\n"
            f"Pos:        ({x:.3f}, {y:.3f}) m\n"
            f"Yaw:        {np.degrees(yaw_rad):.1f}°\n"
            f"RSSI raw:   {rssi_raw_str}\n"
            f"RSSI filt:  {rssi_filt_str}\n"
            f"Samples:    {n}\n"
            f"Beacon est: {beacon_str}"
        )

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def wait_for_feedback(self, prompt: str) -> None:
        """Show a prompt in the GUI and wait for any key press as feedback."""
        self.prompt_txt.set_text(
            f"GUIDE: {prompt}\n"
            "Press any key in this window when done."
        )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        while True:
            if plt.waitforbuttonpress(timeout=0.1):
                break
            self.fig.canvas.flush_events()

    def set_triangle_guide(self, triangle_xy: np.ndarray) -> None:
        """Display triangle waypoints/path on the map."""
        if triangle_xy.shape != (3, 2):
            raise ValueError("triangle_xy must have shape (3, 2)")

        closed = np.vstack([triangle_xy, triangle_xy[0]])
        self.guide_line.set_data(closed[:, 0], closed[:, 1])
        self.guide_pts.set_data(triangle_xy[:, 0], triangle_xy[:, 1])

        # Expand view to include triangle even before sample trajectory exists.
        margin = 0.35
        self.ax_map.set_xlim(
            float(np.min(closed[:, 0]) - margin),
            float(np.max(closed[:, 0]) + margin),
        )
        self.ax_map.set_ylim(
            float(np.min(closed[:, 1]) - margin),
            float(np.max(closed[:, 1]) + margin),
        )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def update_guide_position(
        self,
        x: float,
        y: float,
        target_x: float,
        target_y: float,
        step: int,
        total_steps: int,
        message: str,
    ) -> None:
        """Update live guide prompt with current and target positions."""
        self.guide_current.set_data([x], [y])
        self.guide_target.set_data([target_x], [target_y])
        self.prompt_txt.set_text(
            f"GUIDE [{step}/{total_steps}]: {message}\n"
            f"Target: ({target_x:.3f}, {target_y:.3f}) m\n"
            f"Current: ({x:.3f}, {y:.3f}) m\n"
            "Press any key in this window when you reached the target."
        )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def clear_prompt(self) -> None:
        self.prompt_txt.set_text("")
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def set_objective(self, x: float, y: float, message: str) -> None:
        """Display post-guide objective marker and message."""
        self.objective_xy = (x, y)
        self.objective_dot.set_data([x], [y])
        self.prompt_txt.set_text(
            f"OBJECTIVE: {message}\n"
            f"Objective at ({x:.3f}, {y:.3f}) m"
        )
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


# ---------------------------------------------------------------------------
# BLE MAC helpers
# ---------------------------------------------------------------------------
# The firmware stores the 6-byte MAC address inside a uint64 split across:
#   astra.bound_device_low  (uint32) → MAC bytes [0..3]
#   astra.bound_device_hig  (uint16) → MAC bytes [4..5]
# For user-facing CLI I/O we use canonical MAC order (AA:BB:CC:DD:EE:FF),
# but firmware expects the opposite byte order, so we invert on write/read.
# Writing bound_device_hig triggers the bind/unbind callback in the firmware.

def get_bound_mac(scf) -> str:
    """Read the currently bound BLE MAC from the Crazyflie params.

    Returns a colon-separated uppercase string, e.g. ``'AA:BB:CC:DD:EE:FF'``.
    All-zeros means unbound.
    """
    low = int(scf.cf.param.get_value("astra.bound_device_low"))
    high = int(scf.cf.param.get_value("astra.bound_device_hig"))
    mac_bytes = [
        (low >> 0) & 0xFF,
        (low >> 8) & 0xFF,
        (low >> 16) & 0xFF,
        (low >> 24) & 0xFF,
        (high >> 0) & 0xFF,
        (high >> 8) & 0xFF,
    ]
    mac_bytes.reverse()
    return ":".join(f"{b:02X}" for b in mac_bytes)


def set_bound_mac(scf, mac_str: str) -> None:
    """Write a BLE MAC address to the Crazyflie via the param system.

    Accepts ``'AA:BB:CC:DD:EE:FF'`` or ``'AA-BB-CC-DD-EE-FF'`` format.
    Pass ``'00:00:00:00:00:00'`` to unbind.
    Writing bound_device_low first (no side-effects), then bound_device_hig
    which triggers the firmware bind/unbind callback.
    """
    parts = mac_str.replace("-", ":").split(":")
    if len(parts) != 6:
        raise ValueError(f"Invalid MAC address: {mac_str!r}")
    mac_bytes = [int(b, 16) for b in parts]
    mac_bytes.reverse()
    low = (
        (mac_bytes[0] << 0)
        | (mac_bytes[1] << 8)
        | (mac_bytes[2] << 16)
        | (mac_bytes[3] << 24)
    )
    high = (mac_bytes[4] << 0) | (mac_bytes[5] << 8)
    # Write low first (no callback), then high (triggers bind/unbind on firmware)
    scf.cf.param.set_value("astra.bound_device_low", str(low))
    scf.cf.param.set_value("astra.bound_device_hig", str(high))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_rssi_map(scf, args, data_queue: "queue.Queue[DroneData]") -> None:
    # Reset Kalman and let it settle briefly
    print("Resetting Kalman estimator…")
    scf.cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    scf.cf.param.set_value("kalman.resetEstimation", "0")
    time.sleep(1.0)

    print("Initializing visualizer…")
    viz = RssiMapVisualizer()

    # Manual triangle guidance (the drone does not self-navigate here).
    print("Waiting for first telemetry packet to anchor triangle guide...")
    latest_data = data_queue.get()
    side = args.triangle_side
    h = np.sqrt(3.0) * 0.5 * side
    ax0, ay0 = latest_data.x, latest_data.y
    triangle_xy = np.array(
        [
            [ax0, ay0],
            [ax0 + side, ay0],
            [ax0 + 0.5 * side, ay0 + h],
        ],
        dtype=float,
    )
    viz.set_triangle_guide(triangle_xy)

    triangle_steps = [
        ("Move to vertex A", triangle_xy[0]),
        ("Move from A to vertex B", triangle_xy[1]),
        ("Move from B to vertex C", triangle_xy[2]),
        ("Move from C back to vertex A", triangle_xy[0]),
    ]
    print("Triangle guide: follow GUI prompts and confirm each step with a key press.")
    for i, (message, target) in enumerate(triangle_steps, start=1):
        while True:
            # Drain queue to keep the guide position live.
            try:
                while True:
                    latest_data = data_queue.get_nowait()
            except queue.Empty:
                pass

            viz.update_guide_position(
                latest_data.x,
                latest_data.y,
                float(target[0]),
                float(target[1]),
                step=i,
                total_steps=len(triangle_steps),
                message=message,
            )

            if plt.waitforbuttonpress(timeout=0.1):
                break

    objective_x = float(np.mean(triangle_xy[:, 0]))
    objective_y = float(np.mean(triangle_xy[:, 1]))
    viz.set_objective(
        objective_x,
        objective_y,
        "Continue collecting RSSI samples around the green diamond.",
    )

    rssi_filter = MedianEmaFilter(window_size=5, alpha=0.35)
    rssi_kalman = ScalarKalmanFilter()

    # Accumulated sample history
    xs: list[float] = []
    ys: list[float] = []
    rssi_vals: list[float] = []
    rssi_vals_kalman: list[float] = []
    csv_rows: list[dict] = []

    beacon: Optional[BeaconEstimate] = None
    tick = 0

    print("Collecting data — press Ctrl+C to stop.")
    try:
        while True:
            data: DroneData = data_queue.get()
            yaw_rad = float(np.radians(data.yaw))

            rssi_filt: Optional[float] = None
            if data.rssi_raw != _INVALID_RSSI:
                rssi_raw_f = float(data.rssi_raw)
                rssi_filt = rssi_filter.update(rssi_raw_f)
                rssi_kalman_filt = rssi_kalman.update(rssi_raw_f)
                xs.append(data.x)
                ys.append(data.y)
                rssi_vals.append(rssi_filt)
                rssi_vals_kalman.append(rssi_kalman_filt)
                csv_rows.append(
                    {
                        "t": tick * 0.05,
                        "x": data.x,
                        "y": data.y,
                        "yaw": yaw_rad,
                        "rssi_raw": float(data.rssi_raw),
                        "rssi_filtered": rssi_filt,
                    }
                )

            # Recompute beacon estimate every 30 ticks once we have data
            if tick % 30 == 0 and len(xs) >= 3:
                try:
                    beacon = estimate_beacon_position(
                        np.asarray(xs),
                        np.asarray(ys),
                        np.asarray(rssi_vals_kalman),
                        tx_power_dbm=args.tx_power,
                        path_loss_n=args.path_loss_n,
                    )
                except Exception:
                    beacon = None

            # Refresh visualizer every 3 ticks (~6 Hz at 50 ms period)
            if tick % 3 == 0:
                viz.update(
                    tick,
                    data.x,
                    data.y,
                    yaw_rad,
                    data.rssi_raw,
                    rssi_filt,
                    xs,
                    ys,
                    rssi_vals,
                    beacon,
                )

            tick += 1

    except KeyboardInterrupt:
        print("Stopping…")
    finally:
        if args.save_csv and csv_rows:
            write_csv_rows(args.save_csv, csv_rows)
            print(f"Saved {len(csv_rows)} rows → {args.save_csv}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Live RSSI heatmap for BLE beacon localisation via Crazyflie"
    )
    parser.add_argument(
        "--uri",
        default="radio://0/83/2M/E7E7E7E7EA",
        help="Crazyflie radio URI (default: radio://0/83/2M/E7E7E7E7EA)",
    )
    parser.add_argument(
        "--tx-power",
        type=float,
        default=-59.0,
        help="Beacon TX power at 1 m in dBm used by the log-distance model (default: -59.0)",
    )
    parser.add_argument(
        "--path-loss-n",
        type=float,
        default=2.0,
        help="Path-loss exponent n for the log-distance model (default: 2.0, free-space)",
    )
    parser.add_argument(
        "--save-csv",
        default=None,
        metavar="FILE",
        help="Save (t, x, y, yaw, rssi_raw, rssi_filtered) rows to FILE as CSV on exit",
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    cflib.crtp.init_drivers(enable_debug_driver=True)
    data_queue: "queue.Queue[DroneData]" = queue.Queue()

    def log_callback(timestamp, data, logconf):
        data_queue.put(
            DroneData(
                x=data["stateEstimate.x"],
                y=data["stateEstimate.y"],
                yaw=data["stabilizer.yaw"],
                rssi_raw=int(data["astra.bound_device_rssi"]),
            )
        )

    # 2 + 2 + 2 + 4 = 10 bytes — well within the 26-byte LogConfig limit
    logconf = LogConfig(name="RssiMap", period_in_ms=50)
    logconf.add_variable("stateEstimate.x", "FP16")            # 2 bytes
    logconf.add_variable("stateEstimate.y", "FP16")            # 2 bytes
    logconf.add_variable("stabilizer.yaw", "FP16")             # 2 bytes
    logconf.add_variable("astra.bound_device_rssi", "int32_t") # 4 bytes

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print(f"Connected to {args.uri}")

        # Print firmware DEBUG_PRINT messages directly to console
        fw_log = FirmwareLogAssembler(lambda line: print(f"[CF] {line}", flush=True))
        scf.cf.console.receivedChar.add_callback(fw_log.feed)

        scf.cf.param.set_value("stabilizer.estimator", "1")

        # ---- BLE MAC setup ----
        if args.mac is not None:
            print(f"Setting bound device MAC → {args.mac}")
            set_bound_mac(scf, args.mac)
            time.sleep(0.2)  # allow the firmware callback to run

        current_mac = get_bound_mac(scf)
        if current_mac == "00:00:00:00:00:00":
            print("Bound device: (none — unbound)")
        else:
            print(f"Bound device MAC: {current_mac}")

        scf.cf.log.add_config(logconf)
        logconf.data_received_cb.add_callback(log_callback)
        logconf.start()

        run_rssi_map(scf, args, data_queue)
