import argparse
import logging
import queue
from collections import deque, namedtuple

import numpy as np
import matplotlib

# Force a GUI backend (common fix for windows not appearing)
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

import time

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

from crazyslam.slam import SLAM
from crazyslam.mapping import init_params_dict, discretize, target_cell

# Structured data for the queue
DroneData = namedtuple(
    "DroneData",
    ["front", "right", "back", "left", "x", "y", "yaw", "pitch", "roll"],
)


class RangeProcessor:
    def __init__(self, max_threshold=1.0):
        self.max_threshold = max_threshold
        self.scan_angles = np.array([0, 0.5 * np.pi, np.pi, 1.5 * np.pi]).T

    def clean(self, val):
        if val >= 32766 or val <= 0:
            return self.max_threshold
        return val / 1000.0

    def process_frame(self, data: DroneData):
        ranges = np.array(
            [self.clean(v) for v in [data.front, data.right, data.back, data.left]]
        )
        yaw_rad = np.radians(data.yaw)
        return ranges, yaw_rad


def wrap_angle(angle):
    return np.arctan2(np.sin(angle), np.cos(angle))


class SlamVisualizer:
    def __init__(self, slam_agent, max_range=1.0, sample_period=0.05):
        self.agent = slam_agent
        self.max_range = max_range
        self.sample_period = sample_period
        self.traj_history = 25
        self.prev_tick = None
        self.prev_raw_xy = None
        self.prev_slam_xy = None

        # Initialize Figure
        plt.ion()
        self.fig = plt.figure(figsize=(10, 6))
        self.gs = self.fig.add_gridspec(
            3, 2, width_ratios=[3, 2], height_ratios=[3, 2, 2]
        )

        # 1. Map Plot
        self.ax_map = self.fig.add_subplot(self.gs[:, 0])
        # Fixed log-odds display range avoids all-black rendering from autoscaling.
        self.img = self.ax_map.imshow(
            self.agent.map,
            cmap="gray_r",
            origin="lower",
            vmin=-50,
            vmax=100,
            interpolation="nearest",
        )
        self.fig.colorbar(
            self.img,
            ax=self.ax_map,
            fraction=0.03,
            pad=0.02,
            label="Log-odds (free ← 0 → occupied)",
        )
        (self.traj_line,) = self.ax_map.plot([], [], "r-", lw=1, alpha=0.8)
        (self.pose_dot,) = self.ax_map.plot([], [], "ro", label="SLAM pose")
        (self.beam_dots,) = self.ax_map.plot([], [], "cx", ms=6, mew=1.5)
        self.arrow = None

        # 2. Range Bar Plot
        self.ax_ranges = self.fig.add_subplot(self.gs[0, 1])
        self.bars = self.ax_ranges.bar(
            ["F", "R", "B", "L"], [0] * 4, color=["C0", "C1", "C2", "C3"]
        )
        self.ax_ranges.set_ylim(0, max_range)

        # 3. Stabilizer Angles Plot
        self.ax_gyro = self.fig.add_subplot(self.gs[1, 1])
        self.ax_gyro.set_title("Stabilizer Angles")
        self.ax_gyro.set_ylabel("deg")
        self.ax_gyro.grid(True, alpha=0.3)
        (self.gyro_line_x,) = self.ax_gyro.plot([], [], "C0-", lw=1, label="roll")
        (self.gyro_line_y,) = self.ax_gyro.plot([], [], "C1-", lw=1, label="pitch")
        self.ax_gyro.legend(loc="upper right", fontsize=8)
        self.gyro_ticks = deque(maxlen=120)
        self.gyro_x_vals = deque(maxlen=120)
        self.gyro_y_vals = deque(maxlen=120)

        # 4. Telemetry Text
        self.ax_info = self.fig.add_subplot(self.gs[2, 1])
        self.ax_info.axis("off")
        self.txt = self.ax_info.text(
            0, 1, "Waiting for data...", va="top", family="monospace"
        )

        plt.tight_layout()
        plt.show(block=False)
        plt.pause(0.1)  # Force window to render immediately

    def update(
        self,
        tick,
        x,
        y,
        yaw,
        motion_update,
        ranges,
        scan_angles,
        gyro_vals,
        slam_states,
    ):
        self.img.set_data(self.agent.map)

        if self.prev_tick is None or tick <= self.prev_tick:
            dt = self.sample_period
        else:
            dt = (tick - self.prev_tick) * self.sample_period

        curr_raw_xy = np.array([x, y], dtype=float)
        if self.prev_raw_xy is None:
            raw_velocity = 0.0
        else:
            raw_velocity = np.linalg.norm(curr_raw_xy - self.prev_raw_xy) / max(
                dt, 1e-6
            )

        if len(slam_states) > 0:
            recent_states = slam_states[-self.traj_history :]
            traj_idx = np.array(
                [discretize(s[:2], self.agent.params) for s in recent_states]
            )
            self.traj_line.set_data(traj_idx[:, 1], traj_idx[:, 0])

            slam_state = np.asarray(recent_states[-1]).reshape(3)
            curr_idx = traj_idx[-1]
            self.pose_dot.set_data([curr_idx[1]], [curr_idx[0]])

            beam_targets = target_cell(slam_state, ranges, scan_angles)
            beam_idx = discretize(beam_targets, self.agent.params)
            self.beam_dots.set_data(beam_idx[1], beam_idx[0])

            if self.arrow:
                self.arrow.remove()
            self.arrow = self.ax_map.arrow(
                curr_idx[1],
                curr_idx[0],
                10 * np.sin(slam_state[2]),
                10 * np.cos(slam_state[2]),
                head_width=3,
                color="blue",
            )
            slam_x = slam_state[0]
            slam_y = slam_state[1]
            slam_yaw_deg = np.degrees(slam_state[2])
            curr_slam_xy = slam_state[:2]
            if self.prev_slam_xy is not None:
                slam_velocity = np.linalg.norm(curr_slam_xy - self.prev_slam_xy) / max(
                    dt, 1e-6
                )
            else:
                slam_velocity = 0.0
            self.prev_slam_xy = curr_slam_xy.copy()
        else:
            self.beam_dots.set_data([], [])
            slam_x = float("nan")
            slam_y = float("nan")
            slam_yaw_deg = float("nan")
            slam_velocity = float("nan")

        self.prev_tick = tick
        self.prev_raw_xy = curr_raw_xy.copy()

        for bar, h in zip(self.bars, ranges):
            bar.set_height(h)

        roll, pitch, yaw_deg = gyro_vals
        self.gyro_ticks.append(tick)
        self.gyro_x_vals.append(roll)
        self.gyro_y_vals.append(pitch)
        gyro_ticks = np.array(self.gyro_ticks)
        gyro_x = np.array(self.gyro_x_vals)
        gyro_y = np.array(self.gyro_y_vals)
        self.gyro_line_x.set_data(gyro_ticks, gyro_x)
        self.gyro_line_y.set_data(gyro_ticks, gyro_y)
        if gyro_ticks.size > 0:
            self.ax_gyro.set_xlim(gyro_ticks[0], max(gyro_ticks[0] + 1, gyro_ticks[-1]))
            gyro_max = max(
                1.0, float(np.max(np.abs(np.vstack((gyro_x, gyro_y)))))
            )
            self.ax_gyro.set_ylim(-1.1 * gyro_max, 1.1 * gyro_max)

        self.txt.set_text(
            f"Iteration: {tick}\n"
            f"Raw X: {x:.3f}m | Raw Y: {y:.3f}m\n"
            f"SLAM X: {slam_x:.3f}m | SLAM Y: {slam_y:.3f}m\n"
            f"Raw velocity: {raw_velocity:.5f}m/s\n"
            f"SLAM velocity: {slam_velocity:.5f}m/s\n"
            f"Raw yaw: {np.degrees(yaw):.1f}°\n"
            f"SLAM yaw: {slam_yaw_deg:.1f}°\n"
            f"Roll/Pitch/Yaw: {roll:.1f}, {pitch:.1f}, {yaw_deg:.1f} deg\n"
            f"d_pos: {np.linalg.norm(motion_update[:2]):.3f}m"
        )

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


def wait_for_kalman(scf, timeout=5.0, threshold=0.002):
    """Wait until the Kalman estimator variance has converged.

    Polls stateEstimateZ.varX and varY; returns once both drop below
    `threshold` for two consecutive readings, or after `timeout` seconds.
    """
    print(f"Waiting for Kalman to converge (timeout={timeout}s)...")
    var_x = var_y = float("inf")
    t_start = time.time()

    # Request a quick log of the covariance diagonals
    lc = LogConfig(name="Kalman", period_in_ms=100)
    lc.add_variable("kalman.varPX", "float")
    lc.add_variable("kalman.varPY", "float")

    converge_count = 0

    def _cb(timestamp, data, logconf):
        nonlocal var_x, var_y
        var_x = data["kalman.varPX"]
        var_y = data["kalman.varPY"]

    scf.cf.log.add_config(lc)
    lc.data_received_cb.add_callback(_cb)
    lc.start()

    try:
        while time.time() - t_start < timeout:
            time.sleep(0.1)
            if var_x < threshold and var_y < threshold:
                converge_count += 1
                if converge_count >= 2:
                    print(f"Kalman converged (varX={var_x:.5f}, varY={var_y:.5f})")
                    return
            else:
                converge_count = 0
        print(
            f"Kalman convergence timeout (varX={var_x:.5f}, varY={var_y:.5f}), continuing anyway"
        )
    finally:
        lc.stop()
        lc.delete()


def run_slam(scf, args, data_queue):
    processor = RangeProcessor(max_threshold=args.max_range)
    slam_agent = SLAM(
        params=init_params_dict(args.map_size, args.map_resolution),
        n_particles=int(args.n_particles),
        current_state=np.zeros((3, 1)),
        system_noise_variance=np.diag(
            [args.process_noise_xy, args.process_noise_xy, args.process_noise_yaw]
        ),
        correlation_matrix=np.array([[0, -1], [-1, 10]]),
    )

    # Reset Kalman state and wait for it to converge before starting SLAM
    print("Resetting Kalman estimator...")
    scf.cf.param.set_value("kalman.resetEstimation", "1")
    time.sleep(0.1)
    scf.cf.param.set_value("kalman.resetEstimation", "0")
    wait_for_kalman(scf, timeout=args.kalman_timeout)

    # Initialize Visualizer BEFORE waiting for data
    print("Initializing Visualizer...")
    viz = SlamVisualizer(slam_agent, max_range=args.max_range, sample_period=0.05)

    slam_states = []
    tick = 0

    print("Waiting for first data packet from Crazyflie...")
    first_data = data_queue.get()
    old_pos = np.array([first_data.x, first_data.y, np.radians(first_data.yaw)])

    try:
        while True:
            data = data_queue.get()
            ranges, yaw_rad = processor.process_frame(data)

            curr_pos = np.array([data.x, data.y, yaw_rad])
            motion_update = curr_pos - old_pos
            if args.rotation_only:
                motion_update[:2] = 0.0
            motion_update[2] = wrap_angle(motion_update[2])

            new_state = slam_agent.update_state(
                ranges, processor.scan_angles, motion_update
            )
            slam_states.append(new_state)

            if tick % 5 == 0:
                viz.update(
                    tick,
                    data.x,
                    data.y,
                    yaw_rad,
                    motion_update,
                    ranges,
                    processor.scan_angles,
                    (data.roll, data.pitch, data.yaw),
                    slam_states,
                )

            old_pos = curr_pos
            tick += 1

    except KeyboardInterrupt:
        print("Stopping...")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--n-particles",
        type=int,
        default=400,
        help="Number of particles in the particle filter (default: 400)",
    )
    parser.add_argument(
        "--uri",
        default="radio://0/83/2M/E7E7E7E7EA",
        help="Crazyflie radio URI (default: radio://0/83/2M/E7E7E7E7EA)",
    )
    parser.add_argument(
        "--map-size",
        type=int,
        default=1,
        help="Square map side length in metres (default: 1)",
    )
    parser.add_argument(
        "--map-resolution",
        type=int,
        default=100,
        help="Grid cells per metre (default: 100, i.e. 1 cm/cell)",
    )
    parser.add_argument(
        "--max-range",
        type=float,
        default=0.25,
        help="Sensor range cap in metres; readings above this are clamped (default: 0.25)",
    )
    parser.add_argument(
        "--process-noise-xy",
        type=float,
        default=1e-4,
        help="Per-step variance for SLAM x/y particle noise in m^2 (default: 1e-4)",
    )
    parser.add_argument(
        "--process-noise-yaw",
        type=float,
        default=4e-4,
        help="Per-step variance for SLAM yaw particle noise in rad^2 (default: 4e-4)",
    )
    parser.add_argument(
        "--rotation-only",
        action="store_true",
        help="Ignore x/y motion updates in SLAM and use yaw-only updates; useful when manually rotating in place",
    )
    parser.add_argument(
        "--kalman-timeout",
        type=float,
        default=5.0,
        help="Max seconds to wait for Kalman estimator to converge before starting SLAM (default: 5.0)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    cflib.crtp.init_drivers(enable_debug_driver=True)
    data_queue = queue.Queue()

    def log_callback(timestamp, data, logconf):
        data_queue.put(
            DroneData(
                data["range.front"],
                data["range.right"],
                data["range.back"],
                data["range.left"],
                data["stateEstimate.x"],
                data["stateEstimate.y"],
                data["stabilizer.yaw"],
                data["stabilizer.pitch"],
                data["stabilizer.roll"],
            )
        )

    # Max 26 Bytes
    logconf = LogConfig(name="Stabilizer", period_in_ms=50)

    for angle in ["yaw", "pitch", "roll"]:
        logconf.add_variable(f"stabilizer.{angle}", "FP16")  # 2 bytes each
    for var in ["x", "y"]:
        logconf.add_variable(f"stateEstimate.{var}", "FP16")  # 2 bytes each
    for r in ["front", "back", "left", "right"]:
        logconf.add_variable(f"range.{r}", "uint16_t")  # 2 bytes each

    # Total :

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        print(f"Connected to {args.uri}")
        scf.cf.param.set_value("stabilizer.estimator", "2")
        scf.cf.log.add_config(logconf)
        logconf.data_received_cb.add_callback(log_callback)
        logconf.start()

        run_slam(scf, args, data_queue)
