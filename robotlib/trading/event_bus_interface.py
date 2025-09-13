"""
Интерфейс для системы событий торговой системы
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable
from enum import Enum
import time
import asyncio


class EventType(Enum):
    """Типы событий торговой системы"""
    CANDLE_RECEIVED = "candle_received"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_UPDATED = "portfolio_updated"
    MARKET_STATUS_CHANGED = "market_status_changed"


class TradingEvent:
    """Событие торговой системы"""
    
    def __init__(self, event_type: EventType, data: Dict[str, Any], timestamp: float = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or time.time()
    
    def __repr__(self):
        return f"TradingEvent({self.event_type.value}, {self.data})"


class EventBusable(ABC):
    """Интерфейс для шины событий"""
    
    @abstractmethod
    def subscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        """Подписывается на событие"""
        pass
    
    @abstractmethod
    def unsubscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        """Отписывается от события"""
        pass
    
    @abstractmethod
    async def publish(self, event: TradingEvent) -> None:
        """Публикует событие"""
        pass
    
    @abstractmethod
    def get_subscribers(self, event_type: EventType) -> List[Callable[[TradingEvent], None]]:
        """Получает список подписчиков на событие"""
        pass


class EventBus(EventBusable):
    """Реализация шины событий"""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[TradingEvent], None]]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        """Подписывается на событие"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        """Отписывается от события"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
    
    async def publish(self, event: TradingEvent) -> None:
        """Публикует событие"""
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    if handler is None:
                        continue
                    
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    # Логируем ошибку, но не прерываем обработку других подписчиков
                    print(f"Ошибка в обработчике события {event.event_type}: {e}")
    
    def get_subscribers(self, event_type: EventType) -> List[Callable[[TradingEvent], None]]:
        """Получает список подписчиков на событие"""
        return self._subscribers.get(event_type, [])


class MockEventBus(EventBusable):
    """Мок шины событий для тестирования"""
    
    def __init__(self):
        self._published_events: List[TradingEvent] = []
        self._subscribers: Dict[EventType, List[Callable[[TradingEvent], None]]] = {}
    
    def subscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None:
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
    
    async def publish(self, event: TradingEvent) -> None:
        self._published_events.append(event)
        if event.event_type in self._subscribers:
            for handler in self._subscribers[event.event_type]:
                try:
                    if handler is None:
                        continue
                    
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Ошибка в обработчике события {event.event_type}: {e}")
                    import traceback
                    traceback.print_exc()
    
    def get_subscribers(self, event_type: EventType) -> List[Callable[[TradingEvent], None]]:
        return self._subscribers.get(event_type, [])
    
    def get_published_events(self) -> List[TradingEvent]:
        """Получает все опубликованные события для тестирования"""
        return self._published_events.copy()
