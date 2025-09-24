"""
Интерфейс для визуализатора событий торговой системы
"""
from abc import ABC, abstractmethod
from typing import List, Protocol, Dict, Any, runtime_checkable
from robotlib.trading.events import TradingEvent, EventType
from robotlib.visualization_interfaces import TradingEventSinkable


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
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Необязательная обработка события свечи (по умолчанию — noop)."""
        return None
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        """Необязательная обработка события сигнала (по умолчанию — noop)."""
        return None
    
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



class EventVisualizer(EventVisualizerable):
    """Базовый визуализатор событий"""
    
    def __init__(self):
        pass
        self._running = False
    
    
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
        return None
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        return None
    
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
    
    def __init__(self):
        pass
        self._running = False
        self._handled_events: List[TradingEvent] = []
    
    
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
