import numpy as np
import pytest

from crazyslam.mapping import (
    bresenham_line,
    create_empty_map,
    discretize,
    init_params_dict,
    target_cell,
    update_grid_map,
)


def test_init_params_dict_defaults_origin_to_map_center():
    params = init_params_dict(size=10, resolution=5)

    assert params["origin"] == (25, 25)


def test_discretize_clips_out_of_bounds_coordinates():
    params = init_params_dict(size=2, resolution=2, origin=(1, 1))
    points = np.array([
        [10.0, -10.0, 0.0],
        [10.0, -10.0, 0.0],
    ])

    idx = discretize(points, params)

    assert idx.shape == (2, 3)
    assert np.all(idx >= 0)
    assert np.all(idx <= 3)


def test_target_cell_single_state_returns_explicit_2d_shape():
    state = np.array([0.0, 0.0, 0.0])
    ranges = np.array([1.0, 1.0])
    angles = np.array([0.0, np.pi / 2])

    cells = target_cell(state, ranges, angles)

    assert cells.shape == (2, 2)


def test_target_cell_invalid_ndim_raises_value_error():
    with pytest.raises(ValueError, match="states must have shape"):
        target_cell(np.zeros((3, 2, 1)), np.array([1.0]), np.array([0.0]))


def test_bresenham_line_excludes_start_and_end_points():
    start = np.array([0, 0])
    ends = np.array([[0], [3]])

    path = bresenham_line(start, ends)

    assert path == [(0, 1), (0, 2)]


def test_update_grid_map_handles_no_intermediate_cells():
    params = init_params_dict(size=3, resolution=1, origin=(1, 1))
    grid = create_empty_map(params)
    state = np.array([0.0, 0.0, 0.0])

    updated = update_grid_map(
        grid,
        ranges=np.array([0.0]),
        angles=np.array([0.0]),
        state=state,
        params=params,
    )

    # Same cell is both current position and target for a zero-range hit.
    assert updated[1, 1] > 0
    unaffected = np.delete(updated.reshape(-1), 4)
    assert np.allclose(unaffected, 0.0)
