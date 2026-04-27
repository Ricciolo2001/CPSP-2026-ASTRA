# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

from typing import Optional
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


Anchor = tuple[float, float]


@dataclass(slots=True)
class BeaconEstimate:
    x: float
    y: float
    rmse: float
    samples_used: int
    converged: bool


def grid_search_newton(
    anchors: list[Anchor],
    distances: npt.NDArray[np.number] | list[float],
    initial_guess: Optional[Anchor] = None,
    max_iters: int = 50,
    tol: float = 1e-6,
    damping: float = 0.1,
    weights: Optional[npt.NDArray[np.number] | list[float]] = None,
) -> BeaconEstimate:
    pos = np.asarray(anchors, dtype=float)
    dist = np.asarray(distances, dtype=float)
    n_samples = len(pos)

    if n_samples < 3:
        raise ValueError("At least 3 anchors are required for 2D trilateration.")

    if weights is not None:
        w = np.asarray(weights, dtype=float)
        if w.shape != dist.shape:
            raise ValueError("Weights must have the same shape as distances.")
    else:
        w = np.ones_like(dist)  # Equal weights if not provided

    w = w / np.sum(w)  # Normalize weights to sum to 1

    # Step 1: Find a sensible initial guess
    if initial_guess is not None:
        point = np.asarray(initial_guess, dtype=float)
    else:
        # We solve the linearized system to get a sane starting point.
        # (x_i^2 + y_i^2 - d_i^2) - (x_1^2 + y_1^2 - d_1^2) = 2x(x_i - x_1) + 2y(y_i - y_1)
        A = 2 * (pos[1:] - pos[0])
        b = (
            dist[0] ** 2
            - dist[1:] ** 2
            - np.sum(pos[0] ** 2)
            + np.sum(pos[1:] ** 2, axis=1)
        )
        point, _, rank, _ = np.linalg.lstsq(A, b, rcond=None)
        if rank < 2:
            point = np.mean(pos, axis=0)

    # Step 2: Refine with Gauss-Newton
    converged = False
    for _ in range(max_iters):
        # Calculate residuals: f(x) = ||x - anchor|| - distance
        diff = point[None, :] - pos
        current_distances = np.linalg.norm(diff, axis=1)
        current_distances = np.maximum(current_distances, 1e-9)

        residuals = current_distances - dist

        # Jacobian matrix: partial derivatives of the residual w.r.t x and y
        # J_i = [ (x - x_i)/d_i , (y - y_i)/d_i ]
        jac = diff / current_distances[:, None]

        # Normal Equations: (J^T * J) * step = J^T * residuals
        # We add a small damping factor (Levenberg-Marquardt style) to J^T * J
        # to ensure it remains invertible and steps stay small.
        jtj = jac.T @ (w[:, None] * jac)
        jtj += np.eye(2) * damping
        jtr = jac.T @ (w * residuals)

        try:
            step = np.linalg.solve(jtj, jtr)
        except np.linalg.LinAlgError:
            break

        point -= step

        if np.linalg.norm(step) < tol:
            converged = True
            break

    # Final stats
    final_diff = point[None, :] - pos
    final_residuals = np.linalg.norm(final_diff, axis=1) - dist
    rmse = float(np.sqrt(np.sum(w * final_residuals**2)))

    return BeaconEstimate(
        x=float(point[0]),
        y=float(point[1]),
        rmse=rmse,
        samples_used=n_samples,
        converged=converged,
    )


def trilaterate2d(
    anchors: list[Anchor], distances: list[float]
) -> tuple[tuple[float, float], list[float], float]:
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

    return (float(x), float(y)), residuals.tolist(), float(total_error)
