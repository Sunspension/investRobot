"""
Интерфейс для визуализатора событий торговой системы
"""
from abc import ABC, abstractmethod
from typing import List, Protocol, Dict, Any, runtime_checkable
from robotlib.trading.event_bus_interface import EventBusable, TradingEvent, EventType


class EventVisualizerable(ABC):
    """Интерфейс для визуализатора событий"""
    
    @abstractmethod
    async def start(self) -> None:
        """Запускает визуализатор"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        pass
    
    @abstractmethod
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие свечи"""
        pass
    
    @abstractmethod
    async def handle_signal_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие сигнала"""
        pass
    
    @abstractmethod
    async def handle_order_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие ордера"""
        pass
    
    @abstractmethod
    async def handle_position_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие позиции"""
        pass
    
    @abstractmethod
    async def handle_portfolio_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие портфеля"""
        pass
    
    @abstractmethod
    async def handle_market_status_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие статуса рынка"""
        pass


@runtime_checkable
class VisualizationSinkable(Protocol):
    """Легковесный интерфейс-приемник для прямых вызовов из ядра (без EventBus)."""

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        pass

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
        pass

    async def on_market_status(self, status: Dict[str, Any]) -> None:
        pass


class EventVisualizer(EventVisualizerable):
    """Базовый визуализатор событий"""
    
    def __init__(self, event_bus: EventBusable):
        self._event_bus = event_bus
        self._running = False
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Настраивает обработчики событий"""
        self._event_bus.subscribe(EventType.CANDLE_RECEIVED, self.handle_candle_event)
        self._event_bus.subscribe(EventType.SIGNAL_GENERATED, self.handle_signal_event)
        self._event_bus.subscribe(EventType.ORDER_PLACED, self.handle_order_event)
        self._event_bus.subscribe(EventType.ORDER_FILLED, self.handle_order_event)
        self._event_bus.subscribe(EventType.POSITION_OPENED, self.handle_position_event)
        self._event_bus.subscribe(EventType.POSITION_CLOSED, self.handle_position_event)
        self._event_bus.subscribe(EventType.PORTFOLIO_UPDATED, self.handle_portfolio_event)
        self._event_bus.subscribe(EventType.MARKET_STATUS_CHANGED, self.handle_market_status_event)
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        self._running = True
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        self._running = False
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие свечи"""
        pass
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие сигнала"""
        pass
    
    async def handle_order_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие ордера"""
        pass
    
    async def handle_position_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие позиции"""
        pass
    
    async def handle_portfolio_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие портфеля"""
        pass
    
    async def handle_market_status_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие статуса рынка"""
        pass


class MockEventVisualizer(EventVisualizerable):
    """Мок визуализатора событий для тестирования"""
    
    def __init__(self, event_bus: EventBusable):
        self._event_bus = event_bus
        self._running = False
        self._handled_events: List[TradingEvent] = []
        self._setup_event_handlers()
    
    def _setup_event_handlers(self) -> None:
        """Настраивает обработчики событий"""
        self._event_bus.subscribe(EventType.CANDLE_RECEIVED, self.handle_candle_event)
        self._event_bus.subscribe(EventType.SIGNAL_GENERATED, self.handle_signal_event)
        self._event_bus.subscribe(EventType.ORDER_PLACED, self.handle_order_event)
        self._event_bus.subscribe(EventType.ORDER_FILLED, self.handle_order_event)
        self._event_bus.subscribe(EventType.POSITION_OPENED, self.handle_position_event)
        self._event_bus.subscribe(EventType.POSITION_CLOSED, self.handle_position_event)
        self._event_bus.subscribe(EventType.PORTFOLIO_UPDATED, self.handle_portfolio_event)
        self._event_bus.subscribe(EventType.MARKET_STATUS_CHANGED, self.handle_market_status_event)
    
    async def start(self) -> None:
        self._running = True
    
    async def stop(self) -> None:
        self._running = False
    
    def is_running(self) -> bool:
        return self._running
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    async def handle_order_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    async def handle_position_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    async def handle_portfolio_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    async def handle_market_status_event(self, event: TradingEvent) -> None:
        self._handled_events.append(event)
    
    def get_handled_events(self) -> List[TradingEvent]:
        """Получает все обработанные события для тестирования"""
        return self._handled_events.copy()
