"""
Интерфейсы для визуализации торговой системы
"""
from typing import Dict, Protocol, runtime_checkable, Any
from robotlib.trading.order_types import OrderExecution, OrderIntent


@runtime_checkable
class TradingEventSinkable(Protocol):
    """Легковесный интерфейс-приемник для прямых вызовов из ядра."""

    async def on_candle(self, candle, price: float, figi: str) -> None:
        """Обрабатывает событие свечи"""
        pass

    async def on_signal(self, signal, figi: str, price: float) -> None:
        """Обрабатывает событие сигнала"""
        pass

    async def on_market_status(self, status: Dict[str, Any]) -> None:
        """Обрабатывает событие статуса рынка"""
        pass

    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        """Обрабатывает событие исполнения ордера"""
        pass
