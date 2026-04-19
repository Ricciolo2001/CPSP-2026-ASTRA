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


Anchor = tuple[float, float]


def trilaterate2d(anchors: list[Anchor], distances: list[float]):
    """
    Perform trilateration to estimate the position of a point given its distances
    from multiple anchors. This function uses a least-squares approach to handle
    cases where the distances may not be perfectly accurate.

    Args:
        anchors: A list of tuples representing the (x, y) coordinates of the anchors.
        distances: A list of distances from the point to each anchor.
    Returns:
        A tuple containing:
        - The estimated (x, y) coordinates of the point.
        - A list of residuals (the difference between the estimated distance and the actual distance for each anchor).
        - The total error (the L2 norm of the residuals).
    Raises:
        ValueError: If the number of anchors is less than 3, if the number of
        anchors and distances do not match, if any distance is negative, or
        if the anchors are collinear or too close to each other.
    """

    if len(anchors) < 3:
        raise ValueError("At least 3 anchors are required")
    if len(anchors) != len(distances):
        raise ValueError("The number of anchors and distances must match")
    if any(d < 0 for d in distances):
        raise ValueError("Distances cannot be negative")

    x1, y1 = anchors[0]
    d1 = distances[0]

    A = []
    b = []

    for i in range(1, len(anchors)):
        xi, yi = anchors[i]
        di = distances[i]

        A.append([2 * (xi - x1), 2 * (yi - y1)])
        b.append(d1**2 - di**2 - x1**2 + xi**2 - y1**2 + yi**2)

    A = np.asarray(A, dtype=float)
    b = np.asarray(b, dtype=float)

    if np.linalg.matrix_rank(A) < 2:
        raise ValueError("Anchors are collinear or too close to each other")

    point, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

    residuals = []
    x, y = point

    for (xi, yi), di in zip(anchors, distances):
        d_est = np.sqrt((x - xi) ** 2 + (y - yi) ** 2)
        residuals.append(d_est - di)

    residuals = np.asarray(residuals, dtype=float)
    total_error = np.linalg.norm(residuals)

    return point, residuals, total_error
