"""
Dash визуализатор событий торговой системы
"""
import asyncio
from typing import Optional, Any
from robotlib.trading.event_bus_interface import EventBusable, TradingEvent, EventType
from visualization.event_visualizer_interface import EventVisualizerable
# from visualization.trading_visualizer_adapter import TradingVisualizerAdapter
from robotlib.utils.logger import get_logger


class DashEventVisualizer(EventVisualizerable):
    """Dash визуализатор событий торговой системы"""
    
    def __init__(self, event_bus: EventBusable, figi: str = "FUTIMOEXF000"):
        self._event_bus = event_bus
        self._figi = figi
        self._running = False
        self._logger = get_logger(__name__)
        
        # Адаптер будет создан при необходимости
        self._adapter = None
        
        # Настраиваем обработчики событий
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
        if not self._running:
            # Здесь можно инициализировать Dash приложение
            self._running = True
            self._logger.info("Dash визуализатор событий запущен")
    
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        if self._running:
            # Здесь можно остановить Dash приложение
            self._running = False
            self._logger.info("Dash визуализатор событий остановлен")
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        return self._running
    
    async def handle_candle_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие свечи"""
        if not self._running:
            return
        
        try:
            candle = event.data.get('candle')
            price = event.data.get('price')
            if candle and price:
                # Здесь можно обновить Dash UI
                self._logger.debug(f"Обработана свеча: цена={price}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события свечи: {e}")
    
    async def handle_signal_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие сигнала"""
        if not self._running:
            return
        
        try:
            signal = event.data.get('signal')
            if signal:
                # Здесь можно обновить Dash UI
                self._logger.debug(f"Обработан сигнал: {signal}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события сигнала: {e}")
    
    async def handle_order_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие ордера"""
        if not self._running:
            return
        
        try:
            # Здесь можно добавить логику обработки ордеров
            self._logger.debug(f"Обработано событие ордера: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события ордера: {e}")
    
    async def handle_position_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие позиции"""
        if not self._running:
            return
        
        try:
            # Здесь можно добавить логику обработки позиций
            self._logger.debug(f"Обработано событие позиции: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события позиции: {e}")
    
    async def handle_portfolio_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие портфеля"""
        if not self._running:
            return
        
        try:
            # Здесь можно добавить логику обработки портфеля
            self._logger.debug(f"Обработано событие портфеля: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события портфеля: {e}")
    
    async def handle_market_status_event(self, event: TradingEvent) -> None:
        """Обрабатывает событие статуса рынка"""
        if not self._running:
            return
        
        try:
            # Здесь можно добавить логику обработки статуса рынка
            self._logger.debug(f"Обработано событие статуса рынка: {event.event_type}")
        except Exception as e:
            self._logger.error(f"Ошибка обработки события статуса рынка: {e}")
    
    def get_adapter(self) -> Optional[Any]:
        """Получает адаптер для совместимости"""
        return self._adapter
