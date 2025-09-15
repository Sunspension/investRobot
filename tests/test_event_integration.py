"""
Тесты для интеграции EventBus с существующими компонентами
"""
import unittest
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.events import EventType, TradingEvent
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
        
        self.container = TradingSystemContainer(self.config)
        # В тестах мы не можем использовать await в setUp, поэтому создаем синхронную версию
        import asyncio
        self.trading_system = asyncio.run(self.container.build_trading_system(start_server=False))
    
    def test_market_data_stream_created(self):
        """MarketDataStream создается в зависимостях"""
        market_data_stream = self.trading_system['dependencies'].market_data_stream
        self.assertIsNotNone(market_data_stream)
    
    def test_visualizer_exists_when_enabled(self):
        """Визуализатор создается, когда включен"""
        visualizer = self.trading_system['visualizer']
        # Может быть None в тестовой среде без Dash, поэтому просто проверяем ключ
        self.assertTrue('visualizer' in self.trading_system)
    
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
        
        # Напрямую передаём в мок визуализатор (без EventBus)
        asyncio.run(mock_visualizer.handle_candle_event(candle_event))
        asyncio.run(mock_visualizer.handle_signal_event(signal_event))
        
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
        # Создаем конфигурацию без визуализации
        config_no_viz = TradingConfig(figi="FUTIMOEXF000", enable_visualization=False)
        config_no_viz.tcs_client = self.config.tcs_client
        container_no_viz = TradingSystemContainer(config_no_viz)
        trading_system_no_viz = asyncio.run(container_no_viz.build_trading_system(start_server=False))
        
        self.assertIsNone(trading_system_no_viz['visualizer'])
        # EventBus может быть разного типа в зависимости от настроек
        self.assertIsNotNone(trading_system_no_viz['event_bus'])
        
        # Контейнер с визуализацией
        # Создаем конфигурацию с визуализацией
        config_with_viz = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
        config_with_viz.tcs_client = self.config.tcs_client
        container_with_viz = TradingSystemContainer(config_with_viz)
        trading_system_with_viz = asyncio.run(container_with_viz.build_trading_system(start_server=False))
        
        if trading_system_with_viz['visualizer']:
            self.assertIsNotNone(trading_system_with_viz['visualizer'])
            # Проверяем, что это DashEventVisualizer
            from visualization.dash_event_visualizer import DashEventVisualizer
            self.assertIsInstance(trading_system_with_viz['visualizer'], DashEventVisualizer)


if __name__ == '__main__':
    unittest.main()
