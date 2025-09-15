from __future__ import annotations

from typing import Protocol

from robotlib.signal_types import Signal
from visualization.event_visualizer_interface import VisualizationSinkable


class SignalDispatchable(Protocol):
    async def dispatch_signal(self, signal: Signal, figi: str, price: float) -> None: ...


class VisualizationSignalDispatcher:
    """Dispatcher that forwards signals to a VisualizationSinkable."""

    def __init__(self, sink: VisualizationSinkable) -> None:
        self._sink = sink

    async def dispatch_signal(self, signal: Signal, figi: str, price: float) -> None:
        await self._sink.on_signal(signal, figi, price)


