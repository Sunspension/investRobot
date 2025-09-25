"""
Интерфейсы для визуализации торговой системы
"""
from typing import Dict, Protocol, runtime_checkable, Any
from robotlib.trading.order_types import OrderExecution, OrderIntent


@runtime_checkable
class CandleEventSinkable(Protocol):
    """Интерфейс для обработки событий свечей"""

    async def on_candle(self, candle, price: float, figi: str) -> None:
        """Обрабатывает событие свечи"""
        pass


@runtime_checkable
class OrderEventSinkable(Protocol):
    """Интерфейс для обработки событий ордеров"""

    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        """Обрабатывает событие исполнения ордера"""
        pass


@runtime_checkable
class MarketStatusSinkable(Protocol):
    """Интерфейс для обработки статуса рынка"""

    async def on_market_status(self, status: Dict[str, Any]) -> None:
        """Обрабатывает событие статуса рынка"""
        pass


@runtime_checkable
class SignalSinkable(Protocol):
    """Интерфейс для обработки сигналов"""

    async def on_signal(self, signal, figi: str, price: float) -> None:
        """Обрабатывает событие сигнала"""
        pass


@runtime_checkable
class TradingEventSinkable(CandleEventSinkable, OrderEventSinkable, MarketStatusSinkable, SignalSinkable, Protocol):
    """Легковесный интерфейс-приемник для прямых вызовов из ядра.
    
    Композиция всех специализированных протоколов для компонентов, 
    которые обрабатывают все типы событий.
    """
    pass
