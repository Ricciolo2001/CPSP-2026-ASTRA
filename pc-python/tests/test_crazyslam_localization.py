import numpy as np
import pytest

from crazyslam.localization import (
    compute_effective_n_particles,
    get_correlation_score,
    normalize_weights,
    update_particle_weights,
)


def test_normalize_weights_returns_probability_distribution():
    weights = np.array([10.0, 11.0, 12.0])

    normalized = normalize_weights(weights.copy())

    assert np.isclose(normalized.sum(), 1.0)
    assert np.all(normalized > 0)
    assert np.argmax(normalized) == 2


def test_get_correlation_score_2d_target_cells():
    grid_map = np.array([
        [0.0, 1.0],
        [2.0, 0.0],
    ])
    target_cells = np.array([
        [0, 1],
        [1, 1],
    ])
    correlation_matrix = np.array([
        [0.0, -1.0],
        [0.0, 2.0],
    ])

    score = get_correlation_score(grid_map, target_cells, correlation_matrix)

    assert score == 1


def test_get_correlation_score_invalid_shape_raises_value_error():
    with pytest.raises(ValueError, match="target_cells must have shape"):
        get_correlation_score(np.zeros((2, 2)), np.array([1, 2, 3]), np.eye(2))


def test_update_particle_weights_normalizes_output():
    particles = np.array([
        [0.0, 0.0],
        [0.0, 0.0],
        [0.0, 0.0],
        [0.5, 0.5],
    ])
    grid_map = np.array([
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ])
    params = {"size": 3, "resolution": 1, "origin": (1, 1)}
    ranges = np.array([1.0])
    angles = np.array([0.0])
    correlation_matrix = np.array([
        [0.0, -1.0],
        [0.0, 2.0],
    ])

    updated = update_particle_weights(
        particles=particles,
        correlation_matrix=correlation_matrix,
        grid_map=grid_map,
        map_params=params,
        ranges=ranges,
        angles=angles,
    )

    assert np.isclose(updated[-1, :].sum(), 1.0)
    assert np.all(updated[-1, :] >= 0.0)


def test_compute_effective_n_particles_matches_expected_value():
    weights = np.array([0.5, 0.5])

    effective_n = compute_effective_n_particles(weights)

    assert np.isclose(effective_n, 2.0)
