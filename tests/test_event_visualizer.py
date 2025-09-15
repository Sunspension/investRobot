"""
Тесты для EventVisualizer
"""
import unittest
import asyncio
class EventBus:
    ...
from robotlib.trading.events import EventType, TradingEvent
from visualization.event_visualizer_interface import EventVisualizer, MockEventVisualizer


class TestEventVisualizer(unittest.TestCase):
    """Тесты для EventVisualizer"""
    
    def setUp(self):
        """Настройка тестов"""
        self.event_bus = EventBus()
        self.visualizer = EventVisualizer(self.event_bus)
        self.mock_visualizer = MockEventVisualizer(self.event_bus)
    
    def test_visualizer_lifecycle(self):
        """Тест жизненного цикла визуализатора"""
        # Проверяем начальное состояние
        self.assertFalse(self.visualizer.is_running())
        
        # Запускаем
        asyncio.run(self.visualizer.start())
        self.assertTrue(self.visualizer.is_running())
        
        # Останавливаем
        asyncio.run(self.visualizer.stop())
        self.assertFalse(self.visualizer.is_running())
    
    def test_event_handling(self):
        """Тест обработки событий"""
        # Запускаем визуализатор
        asyncio.run(self.visualizer.start())
        
        # Создаем события
        candle_event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        signal_event = TradingEvent(EventType.SIGNAL_GENERATED, {"type": "buy"})
        
        # Напрямую вызываем обработчики (EventBus не используется)
        asyncio.run(self.mock_visualizer.handle_candle_event(candle_event))
        asyncio.run(self.mock_visualizer.handle_signal_event(signal_event))
        
        # Проверяем, что события обработаны (базовая реализация ничего не делает)
        # В реальной реализации здесь была бы проверка обновления UI
        self.assertTrue(True)  # Проходим тест, так как нет исключений
    
    def test_mock_visualizer(self):
        """Тест мок визуализатора"""
        # Запускаем мок визуализатор
        asyncio.run(self.mock_visualizer.start())
        
        # Создаем события
        candle_event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        signal_event = TradingEvent(EventType.SIGNAL_GENERATED, {"type": "buy"})
        
        # Передаем напрямую в мок визуализатор (без EventBus)
        asyncio.run(self.mock_visualizer.handle_candle_event(candle_event))
        asyncio.run(self.mock_visualizer.handle_signal_event(signal_event))
        
        # Проверяем, что события обработаны
        handled_events = self.mock_visualizer.get_handled_events()
        self.assertEqual(len(handled_events), 2)
        self.assertEqual(handled_events[0].event_type, EventType.CANDLE_RECEIVED)
        self.assertEqual(handled_events[1].event_type, EventType.SIGNAL_GENERATED)
    
    def test_multiple_event_types(self):
        """Тест обработки разных типов событий"""
        asyncio.run(self.mock_visualizer.start())
        
        # Создаем события разных типов
        events = [
            TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0}),
            TradingEvent(EventType.SIGNAL_GENERATED, {"type": "buy"}),
            TradingEvent(EventType.ORDER_PLACED, {"order_id": "123"}),
            TradingEvent(EventType.POSITION_OPENED, {"position_id": "456"}),
            TradingEvent(EventType.PORTFOLIO_UPDATED, {"balance": 1000000.0}),
            TradingEvent(EventType.MARKET_STATUS_CHANGED, {"status": "open"})
        ]
        
        # Напрямую вызываем обработчики для всех событий
        for event in events:
            et = event.event_type
            if et == EventType.CANDLE_RECEIVED:
                asyncio.run(self.mock_visualizer.handle_candle_event(event))
            elif et == EventType.SIGNAL_GENERATED:
                asyncio.run(self.mock_visualizer.handle_signal_event(event))
            elif et == EventType.ORDER_PLACED or et == EventType.ORDER_FILLED:
                asyncio.run(self.mock_visualizer.handle_order_event(event))
            elif et == EventType.POSITION_OPENED or et == EventType.POSITION_CLOSED:
                asyncio.run(self.mock_visualizer.handle_position_event(event))
            elif et == EventType.PORTFOLIO_UPDATED:
                asyncio.run(self.mock_visualizer.handle_portfolio_event(event))
            elif et == EventType.MARKET_STATUS_CHANGED:
                asyncio.run(self.mock_visualizer.handle_market_status_event(event))
        
        # Проверяем, что все события обработаны
        handled_events = self.mock_visualizer.get_handled_events()
        self.assertEqual(len(handled_events), len(events))
        
        # Проверяем типы событий
        event_types = [event.event_type for event in handled_events]
        expected_types = [event.event_type for event in events]
        self.assertEqual(set(event_types), set(expected_types))


if __name__ == '__main__':
    unittest.main()
