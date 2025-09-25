"""
Интерфейсы для визуализатора событий торговой системы
"""
from typing import Protocol, Any, Callable, List
from robotlib.trading.events import TradingEvent


class EventVisualizerable(Protocol):
    """Базовый протокол для визуализатора событий"""
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        ...
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        ...
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        ...


class WebSocketEventVisualizerable(Protocol):
    """Протокол для визуализатора событий, получающего данные через WebSocket"""
    
    async def start(self) -> None:
        """Запускает визуализатор"""
        ...
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        ...
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        ...
    
    def set_snapshot_callback(self, callback: Callable[[], None]) -> None:
        """Устанавливает callback для отправки снэпшотов по требованию"""
        ...



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
