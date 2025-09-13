"""
Тесты для интеграции EventBus с существующими компонентами
"""
import unittest
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.event_bus_interface import EventType, TradingEvent
from visualization.event_visualizer_interface import MockEventVisualizer


class TestEventIntegration(unittest.TestCase):
    """Тесты для интеграции EventBus"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=True
        )
        # Добавляем мок tcs_client для тестов
        from unittest.mock import Mock
        self.config.tcs_client = Mock()
        self.config.tcs_client.token = "test_token"
        self.config.tcs_client.id = "test_account_id"
        self.config.tcs_client.sandbox_token = "test_sandbox_token"
        
        self.container = TradingSystemContainer(self.config, enable_visualization=True)
        # В тестах мы не можем использовать await в setUp, поэтому создаем синхронную версию
        import asyncio
        self.trading_system = asyncio.run(self.container.build_trading_system(start_server=False))
    
    def test_market_data_stream_event_publishing(self):
        """Тест публикации событий MarketDataStream"""
        market_data_stream = self.trading_system['dependencies'].market_data_stream
        
        # Проверяем, что EventBus установлен
        self.assertIsNotNone(market_data_stream._event_bus)
        
        # Проверяем, что это реальный EventBus
        from robotlib.trading.event_bus_interface import EventBus
        self.assertIsInstance(market_data_stream._event_bus, EventBus)
    
    def test_visualizer_event_subscription(self):
        """Тест подписки визуализатора на события"""
        visualizer = self.trading_system['visualizer']
        
        if visualizer:
            # Проверяем, что визуализатор подписан на события
            event_bus = self.trading_system['event_bus']
            
            # Проверяем подписки на основные события
            candle_subscribers = event_bus.get_subscribers(EventType.CANDLE_RECEIVED)
            signal_subscribers = event_bus.get_subscribers(EventType.SIGNAL_GENERATED)
            
            self.assertGreater(len(candle_subscribers), 0)
            self.assertGreater(len(signal_subscribers), 0)
    
    def test_event_flow_integration(self):
        """Тест полного потока событий"""
        # Создаем мок визуализатор для тестирования
        event_bus = self.trading_system['event_bus']
        mock_visualizer = MockEventVisualizer(event_bus)
        
        # Запускаем мок визуализатор
        asyncio.run(mock_visualizer.start())
        
        # Создаем тестовые события
        candle_event = TradingEvent(
            EventType.CANDLE_RECEIVED,
            {
                'candle': None,  # Мок свеча
                'price': 100.0,
                'figi': 'FUTIMOEXF000'
            }
        )
        
        signal_event = TradingEvent(
            EventType.SIGNAL_GENERATED,
            {
                'signal': {'type': 'buy', 'strength': 0.8},
                'figi': 'FUTIMOEXF000',
                'price': 100.0
            }
        )
        
        # Публикуем события
        asyncio.run(event_bus.publish(candle_event))
        asyncio.run(event_bus.publish(signal_event))
        
        # Проверяем, что события были обработаны
        handled_events = mock_visualizer.get_handled_events()
        self.assertEqual(len(handled_events), 2)
        
        # Проверяем типы событий
        event_types = [event.event_type for event in handled_events]
        self.assertIn(EventType.CANDLE_RECEIVED, event_types)
        self.assertIn(EventType.SIGNAL_GENERATED, event_types)
    
    def test_visualizer_lifecycle(self):
        """Тест жизненного цикла визуализатора"""
        visualizer = self.trading_system['visualizer']
        
        if visualizer:
            # Проверяем начальное состояние
            self.assertFalse(visualizer.is_running())
            
            # Запускаем
            asyncio.run(visualizer.start())
            self.assertTrue(visualizer.is_running())
            
            # Останавливаем
            asyncio.run(visualizer.stop())
            self.assertFalse(visualizer.is_running())
    
    def test_di_container_visualization_toggle(self):
        """Тест переключения визуализации в DI контейнере"""
        # Контейнер без визуализации
        container_no_viz = TradingSystemContainer(self.config, enable_visualization=False)
        trading_system_no_viz = asyncio.run(container_no_viz.build_trading_system(start_server=False))
        
        self.assertIsNone(trading_system_no_viz['visualizer'])
        # EventBus может быть разного типа в зависимости от настроек
        from robotlib.trading.event_bus_interface import EventBusable
        self.assertIsInstance(trading_system_no_viz['event_bus'], EventBusable)
        
        # Контейнер с визуализацией
        container_with_viz = TradingSystemContainer(self.config, enable_visualization=True)
        trading_system_with_viz = asyncio.run(container_with_viz.build_trading_system(start_server=False))
        
        if trading_system_with_viz['visualizer']:
            self.assertIsNotNone(trading_system_with_viz['visualizer'])
            # Проверяем, что это DashEventVisualizer
            from visualization.dash_event_visualizer import DashEventVisualizer
            self.assertIsInstance(trading_system_with_viz['visualizer'], DashEventVisualizer)


if __name__ == '__main__':
    unittest.main()
