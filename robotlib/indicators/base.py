"""Incremental indicator interfaces.

Designed for O(1) per-tick updates and minimal state, to be portable to Go.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class Indicator(Protocol):
    """Common protocol for incremental indicators.

    Implementations should keep minimal internal state and provide:
    - update(...): process a new tick and optionally return the current value
    - current(): return the last computed value (or None if not warmed up)
    - is_warm(): whether the indicator has enough data for stable output
    - reset(): clear internal state
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


