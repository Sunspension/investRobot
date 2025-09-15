from __future__ import annotations

from typing import Optional


class IncrementalEMA:
    """Инкрементальная EMA с инициализацией через SMA.

    - period: длина окна n
    - alpha: 2/(n+1)
    - Разогрев: возвращает None до накопления n значений; начальная EMA
      инициализируется SMA(n), далее используется стандартная рекуррентная формула EMA.
    """

    def __init__(
        self,
        period: int,
    ) -> None:
        if period <= 0:
            raise ValueError("period must be positive")
        self._period = period
        self._alpha = 2.0 / (period + 1.0)
        self._ema: Optional[float] = None
        self._warm_count = 0
        self._warm_sum = 0.0

    def update(
        self,
        value: float,
    ) -> Optional[float]:
        # Warm-up phase: accumulate first 'period' values
        if self._ema is None:
            self._warm_sum += value
            self._warm_count += 1
            if self._warm_count < self._period:
                return None
            # Seed EMA with SMA(period)
            self._ema = self._warm_sum / float(self._period)
            return self._ema

        # EMA recurrence
        self._ema = (value - self._ema) * self._alpha + self._ema
        return self._ema

    def current(self) -> Optional[float]:
        return self._ema

    def is_warm(self) -> bool:
        return self._ema is not None

    def reset(self) -> None:
        self._ema = None
        self._warm_count = 0
        self._warm_sum = 0.0


