"""
Интерфейсы для визуализации торговой системы
"""
from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class TradingEventSinkable(Protocol):
    """Легковесный интерфейс-приемник для прямых вызовов из ядра."""

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        """Обрабатывает событие свечи"""
        pass

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
        """Обрабатывает событие сигнала"""
        pass

    async def on_market_status(self, status: Dict[str, Any]) -> None:
        """Обрабатывает событие статуса рынка"""
        pass
