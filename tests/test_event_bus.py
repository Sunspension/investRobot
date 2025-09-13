"""
Тесты для EventBus
"""
import unittest
import asyncio
from robotlib.trading.event_bus_interface import EventBus, MockEventBus, EventType, TradingEvent


class TestEventBus(unittest.TestCase):
    """Тесты для EventBus"""
    
    def setUp(self):
        """Настройка тестов"""
        self.event_bus = EventBus()
        self.mock_event_bus = MockEventBus()
    
    def test_subscribe_and_publish(self):
        """Тест подписки и публикации событий"""
        events_received = []
        
        def handler(event: TradingEvent):
            events_received.append(event)
        
        # Подписываемся на событие
        self.event_bus.subscribe(EventType.CANDLE_RECEIVED, handler)
        
        # Создаем событие
        event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        
        # Публикуем событие
        asyncio.run(self.event_bus.publish(event))
        
        # Проверяем, что событие было получено
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0].event_type, EventType.CANDLE_RECEIVED)
        self.assertEqual(events_received[0].data["price"], 100.0)
    
    def test_multiple_subscribers(self):
        """Тест нескольких подписчиков"""
        events_received_1 = []
        events_received_2 = []
        
        def handler1(event: TradingEvent):
            events_received_1.append(event)
        
        def handler2(event: TradingEvent):
            events_received_2.append(event)
        
        # Подписываемся на одно событие
        self.event_bus.subscribe(EventType.CANDLE_RECEIVED, handler1)
        self.event_bus.subscribe(EventType.CANDLE_RECEIVED, handler2)
        
        # Создаем событие
        event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 200.0})
        
        # Публикуем событие
        asyncio.run(self.event_bus.publish(event))
        
        # Проверяем, что оба обработчика получили событие
        self.assertEqual(len(events_received_1), 1)
        self.assertEqual(len(events_received_2), 1)
    
    def test_unsubscribe(self):
        """Тест отписки от событий"""
        events_received = []
        
        def handler(event: TradingEvent):
            events_received.append(event)
        
        # Подписываемся
        self.event_bus.subscribe(EventType.CANDLE_RECEIVED, handler)
        
        # Публикуем событие
        event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        asyncio.run(self.event_bus.publish(event))
        
        # Проверяем, что событие получено
        self.assertEqual(len(events_received), 1)
        
        # Отписываемся
        self.event_bus.unsubscribe(EventType.CANDLE_RECEIVED, handler)
        
        # Публикуем еще одно событие
        event2 = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 200.0})
        asyncio.run(self.event_bus.publish(event2))
        
        # Проверяем, что событие не получено
        self.assertEqual(len(events_received), 1)
    
    def test_mock_event_bus(self):
        """Тест мок EventBus"""
        events_received = []
        
        def handler(event: TradingEvent):
            events_received.append(event)
        
        # Подписываемся
        self.mock_event_bus.subscribe(EventType.CANDLE_RECEIVED, handler)
        
        # Публикуем событие
        event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        asyncio.run(self.mock_event_bus.publish(event))
        
        # Проверяем через мок
        published_events = self.mock_event_bus.get_published_events()
        self.assertEqual(len(published_events), 1)
        self.assertEqual(published_events[0].event_type, EventType.CANDLE_RECEIVED)


if __name__ == '__main__':
    unittest.main()
