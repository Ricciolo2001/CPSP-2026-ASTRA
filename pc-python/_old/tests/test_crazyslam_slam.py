from unittest.mock import patch

import numpy as np

from crazyslam.slam import SLAM


def test_slam_initializes_uniform_weights_and_threshold_clamp():
    params = {"size": 4, "resolution": 1, "origin": (2, 2)}
    slam = SLAM(
        params=params,
        n_particles=5,
        current_state=np.array([1.0, 2.0, 0.5]),
        system_noise_variance=np.eye(3),
        correlation_matrix=np.eye(2),
    )

    assert slam.particles.shape == (4, 5)
    assert np.allclose(slam.particles[:3, :], np.array([[1.0], [2.0], [0.5]]))
    assert np.allclose(slam.particles[3, :], np.full(5, 0.2))
    assert slam.resampling_threshold == 1


def test_update_state_applies_motion_and_updates_current_state():
    params = {"size": 5, "resolution": 1, "origin": (2, 2)}
    slam = SLAM(
        params=params,
        n_particles=3,
        current_state=np.array([0.0, 0.0, 0.0]),
        system_noise_variance=np.eye(3),
        correlation_matrix=np.eye(2),
    )

    motion_update = np.array([1.0, -1.0, 0.1])
    new_state = np.array([3.0, 4.0, 0.7])
    new_particles = np.zeros((4, 3))

    with patch("crazyslam.slam.update_grid_map", return_value=np.ones((5, 5))) as map_patch, patch(
        "crazyslam.slam.get_state_estimate", return_value=(new_state, new_particles)
    ) as state_patch:
        returned = slam.update_state(
            ranges=np.array([1.0]),
            angles=np.array([0.0]),
            motion_update=motion_update,
        )

    map_patch.assert_called_once()
    state_patch.assert_called_once()
    particles_arg = state_patch.call_args.args[0]
    assert np.allclose(
        particles_arg[:3, :],
        np.tile(motion_update.reshape(3, 1), (1, 3)),
    )
    assert np.allclose(slam.particles, new_particles)
    assert np.allclose(slam.current_state, new_state)
    assert np.allclose(returned, new_state)
