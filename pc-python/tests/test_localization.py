import pytest

from astra.localization import grid_search_newton, trilaterate2d


class TestTrilateration:
    def test_1_point(self):
        with pytest.raises(ValueError):
            trilaterate2d([(0, 0)], [1])

    def test_2_points(self):
        with pytest.raises(ValueError):
            trilaterate2d([(0, 0), (1, 0)], [1, 1])

    def test_3_points(self):
        point, _, _ = trilaterate2d([(0, 0), (1, 0), (0, 1)], [1, 1, 1])
        assert point == pytest.approx((0.5, 0.5))

    def test_4_points(self):
        point, _, _ = trilaterate2d([(0, 0), (1, 0), (0, 1), (1, 1)], [1, 1, 1, 1])
        assert point == pytest.approx((0.5, 0.5))

    def test_inconsistent(self):
        _, _, total_error = trilaterate2d([(0, 0), (1, 0), (0, 1)], [1, 1, 2])
        assert total_error > 1e-6

    def test_negative_distance(self):
        with pytest.raises(ValueError):
            trilaterate2d([(0, 0), (1, 0), (0, 1)], [1, -1, 1])

    def test_collinear(self):
        with pytest.raises(ValueError):
            trilaterate2d([(0, 0), (1, 0), (2, 0)], [1, 1, 1])

    def test_wrong_number_of_distances(self):
        with pytest.raises(ValueError):
            trilaterate2d([(0, 0), (1, 0), (0, 1)], [1, 1])


class TestGridSearch:
    def test_grid_search(self):
        est = grid_search_newton(
            anchors=[(0, 0), (1, 0), (0, 1)], distances=[0.5, 0.5, 0.5]
        )
        assert est.x == pytest.approx(0.5, abs=0.1)
        assert est.y == pytest.approx(0.5, abs=0.1)

    def test_insufficient_samples(self):
        with pytest.raises(ValueError):
            grid_search_newton(anchors=[(0, 0), (1, 0)], distances=[0.5, 0.5])

    def test_mismatched_lengths(self):
        with pytest.raises(ValueError):
            grid_search_newton(anchors=[(0, 0), (1, 0)], distances=[0.5])
