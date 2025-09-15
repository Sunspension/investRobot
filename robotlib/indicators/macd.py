from __future__ import annotations

from typing import Optional

from .base import MACDPoint
from .ema import IncrementalEMA


class IncrementalMACD:
    """Инкрементальный MACD с сигнальной EMA и гистограммой.

    Возвращает None до разогрева обеих EMA цены и сигнальной EMA.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> None:
        if fast_period <= 0 or slow_period <= 0 or signal_period <= 0:
            raise ValueError("периоды должны быть положительными")
        if fast_period >= slow_period:
            # Классический MACD требует fast < slow
            raise ValueError("fast_period должен быть меньше slow_period")
        self._ema_fast = IncrementalEMA(fast_period)
        self._ema_slow = IncrementalEMA(slow_period)
        self._ema_signal = IncrementalEMA(signal_period)
        self._last: Optional[MACDPoint] = None

    def update(self, price: float) -> Optional[MACDPoint]:
        fast = self._ema_fast.update(price)
        slow = self._ema_slow.update(price)
        if fast is None or slow is None:
            return None

        macd_line = fast - slow
        signal = self._ema_signal.update(macd_line)
        if signal is None:
            return None

        histogram = macd_line - signal
        self._last = MACDPoint(macd=macd_line, signal=signal, histogram=histogram)
        return self._last

    def current(self) -> Optional[MACDPoint]:
        return self._last

    def is_warm(self) -> bool:
        return (
            self._ema_fast.is_warm()
            and self._ema_slow.is_warm()
            and self._ema_signal.is_warm()
        )

    def reset(self) -> None:
        self._ema_fast.reset()
        self._ema_slow.reset()
        self._ema_signal.reset()
        self._last = None


