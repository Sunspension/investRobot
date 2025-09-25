from __future__ import annotations

from typing import Protocol

from robotlib.signal_types import Signal
from robotlib.trading_interfaces import TradingEventSinkable


class SignalDispatchable(Protocol):
    async def dispatch_signal(self, signal: Signal, figi: str, price: float) -> None: ...


class VisualizationSignalDispatcher:
    """Dispatcher that forwards signals to a TradingEventSinkable."""

    def __init__(self, sink: TradingEventSinkable) -> None:
        self._sink = sink

    async def dispatch_signal(self, signal: Signal, figi: str, price: float) -> None:
        await self._sink.on_signal(signal, figi, price)


