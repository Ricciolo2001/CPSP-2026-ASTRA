from __future__ import annotations

from collections import deque
from statistics import median


class MedianEmaFilter:
    """Robust RSSI filter: running median followed by EMA."""

    def __init__(self, window_size: int = 5, alpha: float = 0.35):
        if window_size <= 0:
            raise ValueError("window_size must be > 0")
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self._window = deque(maxlen=window_size)
        self._alpha = alpha
        self._ema: float | None = None

    def update(self, rssi: float) -> float:
        self._window.append(float(rssi))
        med = median(self._window)
        if self._ema is None:
            self._ema = med
        else:
            self._ema = self._alpha * med + (1.0 - self._alpha) * self._ema
        assert self._ema is not None
        return self._ema

    @property
    def value(self) -> float | None:
        return self._ema


def rssi_to_distance(
    rssi_dbm: float, tx_power_dbm: float = -40.0, path_loss_n: float = 2.0
) -> float:
    """Log-distance path loss model"""
    if path_loss_n <= 0:
        raise ValueError("path_loss_n must be > 0")
    return 10.0 ** ((tx_power_dbm - float(rssi_dbm)) / (10.0 * path_loss_n))
