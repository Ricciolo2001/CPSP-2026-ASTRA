# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

from typing import Optional
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares


Anchor = tuple[float, float]


@dataclass(slots=True)
class BeaconEstimate:
    x: float
    y: float
    rmse: float
    samples_used: int
    converged: bool
    residuals: list[float] = field(default_factory=list)


def _solve_linear(pos: np.ndarray, dist: np.ndarray) -> np.ndarray:
    """Solve the linearized trilateration system.

    Builds and solves the linear system obtained by subtracting the first
    anchor's equation from the rest. Raises ValueError if anchors are
    collinear. Assumes pos and dist are already validated numpy arrays.
    """
    A = 2 * (pos[1:] - pos[0])
    if np.linalg.matrix_rank(A) < 2:
        raise ValueError("Anchors are collinear or too close to each other")
    b = (
        dist[0] ** 2
        - dist[1:] ** 2
        - np.sum(pos[0] ** 2)
        + np.sum(pos[1:] ** 2, axis=1)
    )
    point, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    return point


def trilaterate_lm(
    anchors: list[Anchor],
    distances: npt.NDArray[np.number] | list[float],
    initial_guess: Optional[Anchor] = None,
    max_iters: int = 50,
    tol: float = 1e-6,
    weights: Optional[npt.NDArray[np.number] | list[float]] = None,
) -> BeaconEstimate:
    """
    Estimate a 2D position from anchor distances using Levenberg-Marquardt.

    Minimizes the sum of squared residuals r_i(p) = ||p - anchor_i|| - distance_i
    iteratively. An initial guess is obtained by solving the linearized system;
    it is then refined with damped Gauss-Newton (Levenberg-Marquardt) steps.
    Handles noisy distances better than the linear approach, and supports
    per-anchor weights to down-weight unreliable measurements.

    Args:
        anchors: (x, y) coordinates of each anchor. At least 3 required.
        distances: Distance from the unknown point to each anchor.
        initial_guess: Starting (x, y) for the solver. If None, derived from
            the linearized system.
        max_iters: Maximum number of Gauss-Newton iterations.
        tol: Convergence threshold on step/cost/gradient norms (xtol/ftol/gtol).
        weights: Per-anchor weights. Useful when some anchors are more
            reliable than others (e.g., based on signal quality). Normalized
            internally to sum to 1. Defaults to uniform weights.

    Returns:
        BeaconEstimate with the estimated position, weighted RMSE, number of
        anchors used, and whether the solver converged within `max_iters`.

    Raises:
        ValueError: If fewer than 3 anchors are given, or weights shape
            does not match distances.
    """
    if any(d < 0 for d in distances):
        raise ValueError(f"Distances cannot be negative: {distances}")
    if len(anchors) < 3:
        raise ValueError("At least 3 anchors are required for trilateration")
    if len(anchors) != len(distances):
        raise ValueError(
            "Number of anchors and distances must match: "
            f"{len(anchors)} anchors vs {len(distances)} distances"
        )
    if weights is not None and len(weights) != len(distances):
        raise ValueError(
            "Weights must have the same length as distances: "
            f"{len(weights)} weights vs {len(distances)} distances"
        )

    pos = np.asarray(anchors, dtype=float)
    dist = np.asarray(distances, dtype=float)
    n_samples = len(pos)

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
        point = _solve_linear(pos, dist)

    # Step 2: Refine with scipy's Levenberg-Marquardt
    # Scale residuals by sqrt(w) so the solver minimises sum(w * r_i^2)
    sqrt_w = np.sqrt(w)

    def weighted_residuals(p: np.ndarray) -> np.ndarray:
        return sqrt_w * (np.linalg.norm(p - pos, axis=1) - dist)

    opt = least_squares(
        weighted_residuals,
        x0=point,
        method="lm",
        xtol=tol,
        ftol=tol,
        gtol=tol,
        max_nfev=max_iters,
    )

    final_residuals = np.linalg.norm(opt.x - pos, axis=1) - dist
    rmse = float(np.sqrt(np.sum(w * final_residuals**2)))

    return BeaconEstimate(
        x=float(opt.x[0]),
        y=float(opt.x[1]),
        rmse=rmse,
        samples_used=n_samples,
        converged=opt.status > 0,
        residuals=final_residuals.tolist(),
    )


def trilaterate_lstsq(
    anchors: list[Anchor], distances: list[float]
) -> BeaconEstimate:
    """
    Estimate a 2D position from anchor distances using linear least squares.

    Linearizes the trilateration equations by subtracting one anchor's equation
    from the rest, eliminating the quadratic terms. The resulting linear system
    is solved directly with least squares. Fast and closed-form, but the
    linearization introduces bias when distances are noisy.

    Args:
        anchors: (x, y) coordinates of each anchor. At least 3 required,
            and they must not be collinear.
        distances: Distance from the unknown point to each anchor.
            Must be non-negative and match the length of `anchors`.

    Returns:
        BeaconEstimate with the estimated position, per-anchor residuals,
        RMSE, number of anchors used, and converged=True (closed-form, always
        produces a result).

    Raises:
        ValueError: If fewer than 3 anchors are given, anchor/distance counts
            differ, any distance is negative, or anchors are collinear.
    """
    if len(anchors) < 3:
        raise ValueError("At least 3 anchors are required")
    if len(anchors) != len(distances):
        raise ValueError("The number of anchors and distances must match")
    if any(d < 0 for d in distances):
        raise ValueError("Distances cannot be negative")

    pos = np.asarray(anchors, dtype=float)
    dist_arr = np.asarray(distances, dtype=float)
    point = _solve_linear(pos, dist_arr)

    x, y = float(point[0]), float(point[1])
    residuals = np.linalg.norm(point - pos, axis=1) - dist_arr
    rmse = float(np.linalg.norm(residuals))

    return BeaconEstimate(
        x=x,
        y=y,
        rmse=rmse,
        samples_used=len(anchors),
        converged=True,
        residuals=residuals.tolist(),
    )
