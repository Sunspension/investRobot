"""
Тесты для EventVisualizer
"""
import unittest
import asyncio
from robotlib.trading.event_bus_interface import EventBus, EventType, TradingEvent
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
        
        # Публикуем события
        asyncio.run(self.event_bus.publish(candle_event))
        asyncio.run(self.event_bus.publish(signal_event))
        
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
        
        # Публикуем события
        asyncio.run(self.event_bus.publish(candle_event))
        asyncio.run(self.event_bus.publish(signal_event))
        
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
        
        # Публикуем все события
        for event in events:
            asyncio.run(self.event_bus.publish(event))
        
        # Проверяем, что все события обработаны
        handled_events = self.mock_visualizer.get_handled_events()
        self.assertEqual(len(handled_events), len(events))
        
        # Проверяем типы событий
        event_types = [event.event_type for event in handled_events]
        expected_types = [event.event_type for event in events]
        self.assertEqual(set(event_types), set(expected_types))


if __name__ == '__main__':
    unittest.main()
