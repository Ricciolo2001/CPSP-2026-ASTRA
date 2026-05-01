# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

import numpy as np
import pytest

from astra.localization import trilaterate_lm, trilaterate_lstsq


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def square_anchors():
    """Four anchors at corners of a 10x10 square, target at (3, 4)."""
    anchors = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    target = (3.0, 4.0)
    distances = [np.hypot(target[0] - x, target[1] - y) for x, y in anchors]
    return anchors, distances, target


@pytest.fixture
def triangle_anchors():
    """Three anchors forming a well-conditioned triangle, target at (2, 3)."""
    anchors = [(0.0, 0.0), (6.0, 0.0), (3.0, 6.0)]
    target = (2.0, 3.0)
    distances = [np.hypot(target[0] - x, target[1] - y) for x, y in anchors]
    return anchors, distances, target


# ---------------------------------------------------------------------------
# Input validation — parametrized over both functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fn", [trilaterate_lstsq, trilaterate_lm])
class TestInputValidation:
    def test_fewer_than_3_anchors_empty(self, fn):
        with pytest.raises(ValueError):
            fn([], [])

    def test_fewer_than_3_anchors_one(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0)], [1])

    def test_fewer_than_3_anchors_two(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0)], [1, 1])

    def test_mismatched_lengths_too_few_distances(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (0, 1)], [1, 1])

    def test_mismatched_lengths_too_many_distances(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (0, 1)], [1, 1, 1, 1])

    def test_negative_distance(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (0, 1)], [1, -1, 1])

    def test_collinear_anchors_evenly_spaced(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (2, 0)], [1, 1, 1])

    def test_collinear_anchors_uneven(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (0.5, 0), (1, 0)], [1, 1, 1])

    def test_nan_in_anchors(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (float("nan"), 0), (0, 1)], [1, 1, 1])

    def test_inf_in_anchors(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (float("inf"), 0), (0, 1)], [1, 1, 1])

    def test_nan_in_distances(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (0, 1)], [1, float("nan"), 1])

    def test_inf_in_distances(self, fn):
        with pytest.raises(ValueError):
            fn([(0, 0), (1, 0), (0, 1)], [1, float("inf"), 1])


# ---------------------------------------------------------------------------
# trilaterate_lstsq
# ---------------------------------------------------------------------------


class TestTrilaterate:
    def test_perfect_distances_3_anchors(self, triangle_anchors):
        anchors, distances, target = triangle_anchors
        result = trilaterate_lstsq(anchors, distances)
        assert (result.x, result.y) == pytest.approx(target, abs=1e-6)

    def test_perfect_distances_4_anchors(self, square_anchors):
        anchors, distances, target = square_anchors
        result = trilaterate_lstsq(anchors, distances)
        assert (result.x, result.y) == pytest.approx(target, abs=1e-6)

    def test_residuals_are_zero_on_perfect_data(self, square_anchors):
        anchors, distances, _ = square_anchors
        result = trilaterate_lstsq(anchors, distances)
        assert result.rmse == pytest.approx(0.0, abs=1e-6)
        assert all(abs(r) < 1e-6 for r in result.residuals)

    def test_inconsistent_distances_gives_nonzero_error(self):
        anchors = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
        distances = [5.0, 5.0, 9.0]  # last distance is inconsistent
        result = trilaterate_lstsq(anchors, distances)
        assert result.rmse > 1e-3

    def test_overdetermined_5_anchors(self):
        target = (4.0, 7.0)
        anchors = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (5.0, 0.0)]
        distances = [np.hypot(target[0] - x, target[1] - y) for x, y in anchors]
        result = trilaterate_lstsq(anchors, distances)
        assert (result.x, result.y) == pytest.approx(target, abs=1e-6)

    def test_large_coordinates(self):
        target = (1e5 + 3.0, 1e5 + 4.0)
        anchors = [(1e5, 1e5), (1e5 + 10, 1e5), (1e5, 1e5 + 10)]
        distances = [np.hypot(target[0] - x, target[1] - y) for x, y in anchors]
        result = trilaterate_lstsq(anchors, distances)
        assert (result.x, result.y) == pytest.approx(target, abs=1e-3)


# ---------------------------------------------------------------------------
# trilaterate_lm
# ---------------------------------------------------------------------------


class TestTrilaterate_LM:
    def test_perfect_distances_3_anchors(self, triangle_anchors):
        anchors, distances, target = triangle_anchors
        result = trilaterate_lm(anchors, distances)
        assert result.x == pytest.approx(target[0], abs=1e-4)
        assert result.y == pytest.approx(target[1], abs=1e-4)

    def test_perfect_distances_4_anchors(self, square_anchors):
        anchors, distances, target = square_anchors
        result = trilaterate_lm(anchors, distances)
        assert result.x == pytest.approx(target[0], abs=1e-4)
        assert result.y == pytest.approx(target[1], abs=1e-4)

    def test_converged_on_clean_data(self, square_anchors):
        anchors, distances, _ = square_anchors
        result = trilaterate_lm(anchors, distances)
        assert result.converged

    def test_rmse_near_zero_on_perfect_data(self, square_anchors):
        anchors, distances, _ = square_anchors
        result = trilaterate_lm(anchors, distances)
        assert result.rmse == pytest.approx(0.0, abs=1e-6)

    def test_samples_used(self, square_anchors):
        anchors, distances, _ = square_anchors
        result = trilaterate_lm(anchors, distances)
        assert result.samples_used == len(anchors)

    def test_noisy_distances(self, square_anchors):
        anchors, distances, target = square_anchors
        rng = np.random.default_rng(42)
        noisy = [d + rng.normal(0, 0.1) for d in distances]
        result = trilaterate_lm(anchors, noisy)
        assert abs(result.x - target[0]) < 1.0
        assert abs(result.y - target[1]) < 1.0
        assert result.rmse < 0.5

    def test_lm_beats_lstsq_on_noisy_data(self, square_anchors):
        anchors, distances, _ = square_anchors
        rng = np.random.default_rng(0)
        noisy = [d + rng.normal(0, 0.2) for d in distances]
        lstsq_result = trilaterate_lstsq(anchors, noisy)
        lm_result = trilaterate_lm(anchors, noisy)
        assert lm_result.rmse <= lstsq_result.rmse + 1e-6  # LM should be at least as good

    def test_custom_initial_guess(self, square_anchors):
        anchors, distances, target = square_anchors
        result = trilaterate_lm(anchors, distances, initial_guess=(5.0, 5.0))
        assert result.x == pytest.approx(target[0], abs=1e-4)
        assert result.y == pytest.approx(target[1], abs=1e-4)

    def test_initial_guess_far_away_still_converges(self, square_anchors):
        anchors, distances, target = square_anchors
        result = trilaterate_lm(anchors, distances, initial_guess=(100.0, 100.0))
        assert result.x == pytest.approx(target[0], abs=1e-2)
        assert result.y == pytest.approx(target[1], abs=1e-2)

    def test_uniform_weights_same_as_no_weights(self, square_anchors):
        anchors, distances, _ = square_anchors
        r1 = trilaterate_lm(anchors, distances)
        r2 = trilaterate_lm(anchors, distances, weights=[1.0, 1.0, 1.0, 1.0])
        assert r1.x == pytest.approx(r2.x, abs=1e-6)
        assert r1.y == pytest.approx(r2.y, abs=1e-6)

    def test_weights_shift_solution_toward_trusted_anchors(self, square_anchors):
        anchors, distances, target = square_anchors
        rng = np.random.default_rng(7)
        noisy = [d + rng.normal(0, 0.5) for d in distances]

        # Down-weight the first anchor heavily
        weights_low = [0.01, 1.0, 1.0, 1.0]
        weights_high = [1.0, 1.0, 1.0, 1.0]

        r_low = trilaterate_lm(anchors, noisy, weights=weights_low)
        r_high = trilaterate_lm(anchors, noisy, weights=weights_high)

        # Solutions should differ when one anchor is strongly down-weighted
        assert not (
            pytest.approx(r_low.x, abs=1e-6) == r_high.x
            and pytest.approx(r_low.y, abs=1e-6) == r_high.y
        )

    def test_weight_shape_mismatch(self):
        anchors = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        distances = [1.0, 1.0, 1.0]
        with pytest.raises(ValueError):
            trilaterate_lm(anchors, distances, weights=[1.0, 1.0])

    def test_zero_weights_raises(self, triangle_anchors):
        anchors, distances, _ = triangle_anchors
        with pytest.raises(ValueError):
            trilaterate_lm(anchors, distances, weights=[0.0, 0.0, 0.0])

    def test_negative_sum_weights_raises(self, triangle_anchors):
        anchors, distances, _ = triangle_anchors
        with pytest.raises(ValueError):
            trilaterate_lm(anchors, distances, weights=[-1.0, -1.0, -1.0])

    def test_initial_guess_wrong_shape_raises(self, triangle_anchors):
        anchors, distances, _ = triangle_anchors
        with pytest.raises(ValueError):
            trilaterate_lm(anchors, distances, initial_guess=(1.0, 2.0, 3.0))

    def test_residuals_are_sqrt_w_scaled(self, square_anchors):
        """Stored residuals should be sqrt(w_i) * raw_r_i, consistent with RMSE."""
        anchors, distances, _ = square_anchors
        w = [1.0, 2.0, 3.0, 4.0]
        result = trilaterate_lm(anchors, distances, weights=w)
        stored = np.array(result.residuals)
        # rmse == sqrt(sum(stored^2)) by construction
        assert result.rmse == pytest.approx(float(np.sqrt(np.sum(stored**2))), abs=1e-9)

    def test_max_iters_1_does_not_crash(self, square_anchors):
        anchors, distances, _ = square_anchors
        result = trilaterate_lm(anchors, distances, max_nfev=1)
        assert np.isfinite(result.x)
        assert np.isfinite(result.y)

    def test_large_coordinates(self):
        target = (1e5 + 3.0, 1e5 + 4.0)
        anchors = [(1e5, 1e5), (1e5 + 10, 1e5), (1e5 + 10, 1e5 + 10), (1e5, 1e5 + 10)]
        distances = [np.hypot(target[0] - x, target[1] - y) for x, y in anchors]
        result = trilaterate_lm(anchors, distances)
        assert result.x == pytest.approx(target[0], abs=1e-3)
        assert result.y == pytest.approx(target[1], abs=1e-3)

    def test_both_functions_agree_on_clean_data(self, square_anchors):
        anchors, distances, _ = square_anchors
        lstsq_result = trilaterate_lstsq(anchors, distances)
        lm_result = trilaterate_lm(anchors, distances)
        assert lm_result.x == pytest.approx(lstsq_result.x, abs=1e-3)
        assert lm_result.y == pytest.approx(lstsq_result.y, abs=1e-3)
