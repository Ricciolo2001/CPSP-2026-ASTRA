from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .rssi import rssi_to_distance


@dataclass(slots=True)
class BeaconEstimate:
    x: float
    y: float
    rmse: float
    samples_used: int


def _residuals(
    point: np.ndarray, positions: np.ndarray, distances: np.ndarray
) -> np.ndarray:
    return np.linalg.norm(positions - point[None, :], axis=1) - distances


def estimate_beacon_position(
    x: np.ndarray,
    y: np.ndarray,
    rssi: np.ndarray,
    *,
    tx_power_dbm: float = -59.0,
    path_loss_n: float = 2.0,
    grid_size: int = 40,
    gauss_newton_iters: int = 20,
) -> BeaconEstimate:
    """Estimate beacon 2D position from samples collected by the drone.

    Strategy:
    1. convert RSSI to distance using a log-distance model
    2. coarse grid search inside the explored bounding box
    3. a few Gauss-Newton refinement steps
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rssi = np.asarray(rssi, dtype=float)

    if len(x) != len(y) or len(x) != len(rssi):
        raise ValueError("x, y and rssi must have the same length")
    if len(x) < 3:
        raise ValueError("At least 3 samples are required")

    positions = np.column_stack([x, y])
    distances = np.asarray(
        [
            rssi_to_distance(v, tx_power_dbm=tx_power_dbm, path_loss_n=path_loss_n)
            for v in rssi
        ],
        dtype=float,
    )

    min_x, max_x = float(np.min(x)), float(np.max(x))
    min_y, max_y = float(np.min(y)), float(np.max(y))
    pad = max(0.25, 0.15 * max(max_x - min_x, max_y - min_y, 1.0))
    gx = np.linspace(min_x - pad, max_x + pad, grid_size)
    gy = np.linspace(min_y - pad, max_y + pad, grid_size)

    best_point = np.array([float(np.mean(x)), float(np.mean(y))], dtype=float)
    best_cost = float("inf")
    for px in gx:
        for py in gy:
            point = np.array([px, py], dtype=float)
            residual = _residuals(point, positions, distances)
            cost = float(np.mean(residual**2))
            if cost < best_cost:
                best_cost = cost
                best_point = point

    point = best_point.copy()
    for _ in range(gauss_newton_iters):
        diff = point[None, :] - positions
        norms = np.linalg.norm(diff, axis=1)
        norms = np.maximum(norms, 1e-9)
        residual = norms - distances
        jac = diff / norms[:, None]
        step, *_ = np.linalg.lstsq(jac, residual, rcond=None)
        point = point - step
        if np.linalg.norm(step) < 1e-6:
            break

    final_residual = _residuals(point, positions, distances)
    rmse = float(np.sqrt(np.mean(final_residual**2)))
    return BeaconEstimate(
        x=float(point[0]), y=float(point[1]), rmse=rmse, samples_used=len(x)
    )
