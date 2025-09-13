"""
Тесты для примера использования торговой системы с DI
"""
import unittest
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventBus, MockEventBus


class TestTradingSystemWithDI(unittest.TestCase):
    """Тесты для примера использования торговой системы с DI"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=False
        )
    
    def test_container_creation(self):
        """Тест создания контейнера"""
        container = TradingSystemContainer(self.config, enable_visualization=False)
        self.assertIsInstance(container, TradingSystemContainer)
        self.assertEqual(container._config, self.config)
        self.assertFalse(container._enable_visualization)
    
    def test_trading_system_build(self):
        """Тест сборки торговой системы"""
        container = TradingSystemContainer(self.config, enable_visualization=False)
        trading_system = container.build_trading_system()
        
        # Проверяем, что все компоненты присутствуют
        self.assertIn('config', trading_system)
        self.assertIn('event_bus', trading_system)
        self.assertIn('session_controller', trading_system)
        self.assertIn('dependencies', trading_system)
        self.assertIn('visualizer', trading_system)
        
        # Проверяем типы
        self.assertIsInstance(trading_system['event_bus'], MockEventBus)
        self.assertIsNone(trading_system['visualizer'])  # Визуализация отключена
    
    def test_trading_system_with_visualization(self):
        """Тест торговой системы с визуализацией"""
        container = TradingSystemContainer(self.config, enable_visualization=True)
        trading_system = container.build_trading_system()
        
        # Проверяем, что event_bus - это реальный EventBus
        self.assertIsInstance(trading_system['event_bus'], EventBus)
        
        # Визуализатор может быть None, если модуль недоступен
        # Но это нормально для тестов
    
    def test_singleton_behavior(self):
        """Тест синглтон поведения"""
        container = TradingSystemContainer(self.config, enable_visualization=False)
        
        # Получаем компоненты дважды
        event_bus1 = container.get_event_bus()
        event_bus2 = container.get_event_bus()
        
        # Проверяем, что это один и тот же объект
        self.assertIs(event_bus1, event_bus2)
        
        # Проверяем, что build_trading_system возвращает те же объекты
        trading_system = container.build_trading_system()
        self.assertIs(trading_system['event_bus'], event_bus1)
    
    def test_dependencies_injection(self):
        """Тест инжекции зависимостей"""
        container = TradingSystemContainer(self.config, enable_visualization=False)
        trading_system = container.build_trading_system()
        
        dependencies = trading_system['dependencies']
        
        # Проверяем, что все зависимости созданы
        # api_client может быть None, так как инжектируется позже
        self.assertIsNotNone(dependencies.session_stats)
        self.assertIsNotNone(dependencies.portfolio_manager)
        self.assertIsNotNone(dependencies.risk_manager)
        self.assertIsNotNone(dependencies.order_executor)
        self.assertIsNotNone(dependencies.market_data_stream)
        self.assertIsNotNone(dependencies.signal_manager)
        self.assertIsNotNone(dependencies.strategy_manager)
        
        # Проверяем, что session_initializer установлен
        # session_initializer может быть None, так как устанавливается позже
        # Но мы можем проверить, что он был установлен через get_session_initializer
        session_initializer = container.get_session_initializer()
        self.assertIsNotNone(session_initializer)
    
    def test_event_bus_integration(self):
        """Тест интеграции с шиной событий"""
        container = TradingSystemContainer(self.config, enable_visualization=True)
        trading_system = container.build_trading_system()
        
        event_bus = trading_system['event_bus']
        
        # Проверяем, что это реальный EventBus
        self.assertIsInstance(event_bus, EventBus)
        
        # Проверяем, что можно подписаться на события
        events_received = []
        
        def handler(event):
            events_received.append(event)
        
        from robotlib.trading.event_bus_interface import EventType, TradingEvent
        
        event_bus.subscribe(EventType.CANDLE_RECEIVED, handler)
        
        # Создаем и публикуем событие
        event = TradingEvent(EventType.CANDLE_RECEIVED, {"price": 100.0})
        asyncio.run(event_bus.publish(event))
        
        # Проверяем, что событие было получено
        self.assertEqual(len(events_received), 1)
        self.assertEqual(events_received[0].event_type, EventType.CANDLE_RECEIVED)


if __name__ == '__main__':
    unittest.main()
