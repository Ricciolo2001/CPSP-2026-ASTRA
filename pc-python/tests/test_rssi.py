# SPDX-FileCopyrightText: 2026 Alessandro Ricci
# SPDX-FileCopyrightText: 2026 Eyad Issa
# SPDX-FileCopyrightText: 2026 Giulia Pareschi
#
# SPDX-License-Identifier: MIT

import pytest

from astra.rssi import MedianEmaFilter, rssi_to_distance


class TestRssiToDistance:
    def test_zero_path_loss(self):
        with pytest.raises(ValueError):
            rssi_to_distance(-50, path_loss=0)

    def test_negative_path_loss(self):
        with pytest.raises(ValueError):
            rssi_to_distance(-50, path_loss=-2)

    def test_distance_calculation(self):
        assert rssi_to_distance(-40, tx_power_dbm=-40, path_loss=2) == pytest.approx(
            1.0
        )
        assert rssi_to_distance(-50, tx_power_dbm=-40, path_loss=2) == pytest.approx(
            3.1622776601683795
        )
        assert rssi_to_distance(-60, tx_power_dbm=-40, path_loss=2) == pytest.approx(
            10.0
        )


class TestEmaFilter:
    def test_invalid_window_size(self):
        with pytest.raises(ValueError):
            MedianEmaFilter(window_size=0)

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            MedianEmaFilter(alpha=0)
        with pytest.raises(ValueError):
            MedianEmaFilter(alpha=1.5)

    def test_value_before_update(self):
        filter = MedianEmaFilter(window_size=3, alpha=0.5)
        with pytest.raises(ValueError):
            _ = filter.value

    def test_filter_behavior(self):
        filter = MedianEmaFilter(window_size=3, alpha=0.5)
        assert filter.update(-50) == -50
        assert filter.value == -50
        assert filter.update(-40) == -47.5
        assert filter.value == -47.5
        assert filter.update(-30) == -43.75
        assert filter.value == -43.75
        assert filter.update(-20) == -36.875
        assert filter.value == -36.875
