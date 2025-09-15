from __future__ import annotations

from typing import Optional


class IncrementalATR:
    """Инкрементальный ATR с сглаживанием Уайлдера.

    Разогрев: аккумулирует TR за 'period' баров для начального ATR как SMA(TR).
    Далее: ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
    """

    def __init__(
        self,
        period: int = 14,
    ) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self._period = period
        self._prev_close: Optional[float] = None
        self._atr: Optional[float] = None
        self._warm_sum_tr = 0.0
        self._warm_count = 0

    @staticmethod
    def _true_range(
        high: float,
        low: float,
        prev_close: Optional[float],
    ) -> float:
        if prev_close is None:
            return float(high - low)
        hl = float(high - low)
        hc = abs(float(high - prev_close))
        lc = abs(float(low - prev_close))
        return max(hl, hc, lc)

    def update(
        self,
        high: float,
        low: float,
        close: float,
    ) -> Optional[float]:
        tr = self._true_range(high, low, self._prev_close)
        self._prev_close = float(close)

        # Warm-up: accumulate SMA of TR for the initial ATR
        if self._atr is None:
            self._warm_sum_tr += tr
            self._warm_count += 1
            if self._warm_count < self._period:
                return None
            self._atr = self._warm_sum_tr / float(self._period)
            return self._atr

        # Wilder smoothing
        self._atr = ((self._atr * (self._period - 1)) + tr) / float(self._period)
        return self._atr

    def current(self) -> Optional[float]:
        return self._atr

    def is_warm(self) -> bool:
        return self._atr is not None

    def reset(self) -> None:
        self._prev_close = None
        self._atr = None
        self._warm_sum_tr = 0.0
        self._warm_count = 0


