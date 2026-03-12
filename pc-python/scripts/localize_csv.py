#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from astra.io import read_csv_rows
from astra.localization import estimate_beacon_position


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate beacon position from a telemetry CSV log.")
    parser.add_argument("csv_path", help="Telemetry CSV path")
    parser.add_argument("--tx-power", type=float, default=-59.0, help="Beacon RSSI at 1 meter [dBm]")
    parser.add_argument("--path-loss", type=float, default=2.0, help="Path loss exponent")
    parser.add_argument("--plot", action="store_true", help="Show a 2D plot of samples and estimate")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_csv_rows(args.csv_path)
    if len(rows) < 3:
        raise SystemExit("Need at least 3 samples in the CSV file")

    x = np.array([row["x"] for row in rows], dtype=float)
    y = np.array([row["y"] for row in rows], dtype=float)
    rssi_filtered = np.array([row["rssi_filtered"] for row in rows], dtype=float)

    estimate = estimate_beacon_position(
        x,
        y,
        rssi_filtered,
        tx_power_dbm=args.tx_power,
        path_loss_n=args.path_loss,
    )

    print(f"CSV: {Path(args.csv_path).resolve()}")
    print(f"Beacon estimate: x={estimate.x:.3f} m, y={estimate.y:.3f} m")
    print(f"RMSE: {estimate.rmse:.3f} m using {estimate.samples_used} samples")

    if args.plot:
        plt.figure(figsize=(7, 6))
        scatter = plt.scatter(x, y, c=rssi_filtered)
        plt.scatter([estimate.x], [estimate.y], marker="x", s=150)
        plt.plot(x, y)
        plt.xlabel("x [m]")
        plt.ylabel("y [m]")
        plt.title("ASTRA beacon localization from CSV log")
        plt.axis("equal")
        plt.colorbar(scatter, label="filtered RSSI [dBm]")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
