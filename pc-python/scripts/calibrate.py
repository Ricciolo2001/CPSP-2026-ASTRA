# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

import argparse
import collections
import logging
import sys
import threading
import time
import tkinter as tk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec

import cflib
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.log import LogConfig
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

import astra.console
from astra.crazyflie import check_crazyradio, get_bound_mac, set_bound_mac
from astra.rssi import MedianEmaFilter, rssi_to_distance

DEFAULT_TX_POWER = -40.0
DEFAULT_PATH_LOSS_N = 2.0
DEFAULT_ALPHA = 0.15
DEFAULT_SAMPLE_NUM = 30
DEFAULT_SAMPLE_INTERVAL_MS = 100
HISTORY_LEN = 300  # number of samples to show on the graph

logger = logging.getLogger(__name__)


# ── Shared state (written by CF thread, read by GUI thread) ──────────────────
class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.timestamps = collections.deque(maxlen=HISTORY_LEN)
        self.rssi_raw = collections.deque(maxlen=HISTORY_LEN)
        self.rssi_filt = collections.deque(maxlen=HISTORY_LEN)
        self.distances = collections.deque(maxlen=HISTORY_LEN)
        self.battery = 0
        self.latest_rssi = None
        self.latest_dist = None
        self.connected = False
        self.mac = "—"
        self.t0 = time.time()

    def push(self, ts, rssi_raw, rssi_filt, distance, battery):
        with self.lock:
            self.timestamps.append(ts)
            self.rssi_raw.append(rssi_raw)
            self.rssi_filt.append(rssi_filt)
            self.distances.append(distance)
            self.battery = battery
            self.latest_rssi = rssi_filt
            self.latest_dist = distance

    def snapshot(self):
        with self.lock:
            return (
                list(self.timestamps),
                list(self.rssi_raw),
                list(self.rssi_filt),
                list(self.distances),
                self.battery,
                self.latest_rssi,
                self.latest_dist,
                self.connected,
                self.mac,
            )


# ── Crazyflie worker (runs in its own thread) ────────────────────────────────
def cf_worker(args, state: SharedState):
    astra.console.basic_config(level=logging.INFO)
    cflib.crtp.init_drivers()

    if not check_crazyradio():
        logger.error("Crazyradio not found or failed to initialize.")
        return

    with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
        with state.lock:
            state.connected = True
        logger.info(f"Connected to {args.uri}")

        fw_log = astra.console.LineBuffer(lambda line: logger.debug(f"[CF]: {line}"))
        scf.cf.console.receivedChar.add_callback(fw_log.feed)
        scf.cf.param.set_value("stabilizer.estimator", "2")

        set_bound_mac(scf, args.BLE_MAC)
        time.sleep(0.2)
        current_mac = get_bound_mac(scf)
        with state.lock:
            state.mac = current_mac
        logger.info(f"Bound to MAC: {current_mac}")

        rssi_filter = MedianEmaFilter(window_size=args.sample_num, alpha=args.alpha)

        def _log(ts, data, _):
            rssi = data["astra.bound_device_rssi"]
            battery = data["pm.batteryLevel"]
            rssi_filter.update(rssi)
            filt = rssi_filter.value
            distance = rssi_to_distance(
                filt,
                tx_power_dbm=args.tx_power,
                path_loss=args.path_loss,
            )
            state.push(
                ts / 1000.0,
                rssi if rssi != -1 else float("nan"),
                filt,
                distance,
                battery,
            )

            if rssi == -1:
                logger.info(f"\tt={ts / 1000:.2f} s\t RSSI=No signal\tbat={battery}%")
            else:
                logger.info(
                    f"\tt={ts / 1000:.2f} s\t RSSI={rssi} dBm\t"
                    f" filtered={filt:.2f} dBm\t distance={distance:.2f} m\tbat={battery}%"
                )

        log_conf = LogConfig(name="rssi_sample", period_in_ms=args.sample_interval)
        log_conf.add_variable("astra.bound_device_rssi", "int32_t")
        log_conf.add_variable("pm.batteryLevel", "uint8_t")
        log_conf.data_received_cb.add_callback(_log)

        scf.cf.log.add_config(log_conf)
        try:
            log_conf.start()
            logger.info("Logging RSSI samples… Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log_conf.stop()

    with state.lock:
        state.connected = False


# ── GUI ───────────────────────────────────────────────────────────────────────
DARK_BG = "#0d0f14"
PANEL_BG = "#13161e"
ACCENT = "#00e5ff"
ACCENT2 = "#ff4f7b"
MUTED = "#3a3f52"
TEXT_PRI = "#e8eaf6"
TEXT_SEC = "#7986cb"
FONT_MONO = ("JetBrains Mono", 10) if sys.platform != "darwin" else ("Menlo", 10)


def build_gui(_args, state: SharedState):
    root = tk.Tk()
    root.title("ASTRA · RSSI Monitor")
    root.configure(bg=DARK_BG)
    root.geometry("1000x680")
    root.minsize(800, 540)

    # ── Top status bar ────────────────────────────────────────────────────
    status_bar = tk.Frame(root, bg=PANEL_BG, pady=8, padx=16)
    status_bar.pack(fill="x", side="top")

    tk.Label(
        status_bar,
        text="ASTRA",
        bg=PANEL_BG,
        fg=ACCENT,
        font=("Courier New", 14, "bold"),
    ).pack(side="left")
    tk.Label(
        status_bar,
        text=" · RSSI Monitor",
        bg=PANEL_BG,
        fg=TEXT_SEC,
        font=("Courier New", 11),
    ).pack(side="left")

    conn_dot = tk.Label(status_bar, text="●", bg=PANEL_BG, fg=MUTED, font=("Arial", 14))
    conn_dot.pack(side="right", padx=(4, 0))
    conn_label = tk.Label(
        status_bar, text="Disconnected", bg=PANEL_BG, fg=TEXT_SEC, font=FONT_MONO
    )
    conn_label.pack(side="right")

    # ── KPI tiles row ─────────────────────────────────────────────────────
    tiles_frame = tk.Frame(root, bg=DARK_BG, pady=10, padx=12)
    tiles_frame.pack(fill="x")

    def make_tile(parent, label):
        f = tk.Frame(
            parent,
            bg=PANEL_BG,
            padx=16,
            pady=10,
            highlightbackground=MUTED,
            highlightthickness=1,
        )
        f.pack(side="left", expand=True, fill="both", padx=6)
        tk.Label(
            f, text=label, bg=PANEL_BG, fg=TEXT_SEC, font=("Courier New", 8, "bold")
        ).pack(anchor="w")
        val = tk.Label(
            f, text="—", bg=PANEL_BG, fg=TEXT_PRI, font=("Courier New", 22, "bold")
        )
        val.pack(anchor="w")
        return val

    rssi_val = make_tile(tiles_frame, "RSSI (FILTERED)")
    dist_val = make_tile(tiles_frame, "DISTANCE")
    bat_val = make_tile(tiles_frame, "BATTERY")
    mac_val = make_tile(tiles_frame, "BOUND MAC")

    # ── Matplotlib figure ─────────────────────────────────────────────────
    fig = plt.Figure(figsize=(10, 4.5), facecolor=DARK_BG)
    gs = GridSpec(
        2, 1, figure=fig, hspace=0.35, left=0.07, right=0.97, top=0.93, bottom=0.1
    )

    ax_rssi = fig.add_subplot(gs[0])
    ax_dist = fig.add_subplot(gs[1])

    for ax, title, ylabel, color in [
        (ax_rssi, "RSSI over Time", "dBm", ACCENT),
        (ax_dist, "Estimated Distance", "m", ACCENT2),
    ]:
        ax.set_facecolor(PANEL_BG)
        ax.tick_params(colors=TEXT_SEC, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(MUTED)
        ax.set_title(
            title, color=TEXT_SEC, fontsize=9, loc="left", fontfamily="monospace", pad=4
        )
        ax.set_ylabel(ylabel, color=TEXT_SEC, fontsize=8)
        ax.set_xlabel("time (s)", color=TEXT_SEC, fontsize=8)
        ax.grid(True, color=MUTED, linewidth=0.4, linestyle="--")

    (line_raw,) = ax_rssi.plot([], [], color=MUTED, lw=1, label="raw", alpha=0.6)
    (line_filt,) = ax_rssi.plot([], [], color=ACCENT, lw=1.8, label="filtered")
    (line_dist,) = ax_dist.plot([], [], color=ACCENT2, lw=1.8)
    ax_rssi.legend(
        facecolor=PANEL_BG,
        edgecolor=MUTED,
        labelcolor=TEXT_PRI,
        fontsize=8,
        loc="upper right",
    )

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(0, 12))

    # ── Animation callback ────────────────────────────────────────────────
    def _update(_frame):
        ts, r_raw, r_filt, dists, bat, lat_rssi, lat_dist, connected, mac = (
            state.snapshot()
        )

        # Status dot
        if connected:
            conn_dot.config(fg=ACCENT)
            conn_label.config(text="Connected", fg=ACCENT)
        else:
            conn_dot.config(fg="#ff4444")
            conn_label.config(text="Disconnected", fg="#ff4444")

        # KPI tiles
        rssi_val.config(text=f"{lat_rssi:.1f} dBm" if lat_rssi is not None else "—")
        dist_val.config(text=f"{lat_dist:.2f} m" if lat_dist is not None else "—")
        bat_val.config(text=f"{bat}%")
        mac_val.config(text=mac, font=("Courier New", 11, "bold"))

        if len(ts) < 2:
            return line_raw, line_filt, line_dist

        t0 = ts[0]
        rel = [t - t0 for t in ts]

        line_raw.set_data(rel, r_raw)
        line_filt.set_data(rel, r_filt)
        line_dist.set_data(rel, dists)

        for ax, ys in [(ax_rssi, r_filt + r_raw), (ax_dist, dists)]:
            valid = [y for y in ys if y == y]  # filter NaN
            if valid:
                lo, hi = min(valid), max(valid)
                pad = max((hi - lo) * 0.15, 1.0)
                ax.set_ylim(lo - pad, hi + pad)
            ax.set_xlim(rel[0], max(rel[-1], 5))

        canvas.draw_idle()
        return line_raw, line_filt, line_dist

    ani = animation.FuncAnimation(  # noqa: F841 (keep reference alive)
        fig, _update, interval=300, blit=False, cache_frame_data=False
    )

    root.protocol("WM_DELETE_WINDOW", lambda: (root.destroy(), sys.exit(0)))
    return root, ani


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "BLE_MAC",
        help="BLE MAC address of the beacon to track (e.g. AA:BB:CC:DD:EE:FF)",
    )
    parser.add_argument("--uri", default="radio://0/83/2M/E7E7E7E7EA")
    parser.add_argument("--tx-power", type=float, default=DEFAULT_TX_POWER)
    parser.add_argument("--path-loss", type=float, default=DEFAULT_PATH_LOSS_N)
    parser.add_argument(
        "--sample-interval", type=int, default=DEFAULT_SAMPLE_INTERVAL_MS
    )
    parser.add_argument("--sample-num", type=int, default=DEFAULT_SAMPLE_NUM)
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    state = SharedState()

    # Launch the Crazyflie worker in a daemon thread so it dies with the GUI
    worker = threading.Thread(target=cf_worker, args=(args, state), daemon=True)
    worker.start()

    root, _ani = build_gui(args, state)
    root.mainloop()


if __name__ == "__main__":
    main()
