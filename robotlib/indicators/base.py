"""Интерфейсы инкрементальных индикаторов.

Ориентированы на O(1) обновление на тик и минимальное состояние; легко
переносимы на Go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class Indicator(Protocol):
    """Общий протокол для инкрементальных индикаторов.

    Реализации держат минимальное состояние и предоставляют методы:
    - update(...): обработка тика и возврат текущего значения (или None до разогрева)
    - current(): последнее значение (или None)
    - is_warm(): индикатор разогрет и стабилен
    - reset(): очистка состояния
    """

    def update(self, *args: Any, **kwargs: Any) -> Optional[Any]:
        ...

    def current(self) -> Optional[Any]:
        ...

    def is_warm(self) -> bool:
        ...

    def reset(self) -> None:
        ...


@dataclass(frozen=True)
class MACDPoint:
    macd: float
    signal: float
    histogram: float


