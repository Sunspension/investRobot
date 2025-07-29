#!/usr/bin/env python3
"""
Тесты для интеграции визуализатора с торговой системой
"""
import unittest
import asyncio
from datetime import datetime
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.visualizer_interface import MockTradingVisualizer


class TestVisualizerIntegration(unittest.TestCase):
    """Тесты интеграции визуализатора"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=True
        )
        self.factory = TradingVisualizerFactory()
    
    def test_visualizer_factory_creates_visualizer_when_enabled(self):
        """Тест создания визуализатора когда включен"""
        visualizer = self.factory.create_visualizer(self.config)
        self.assertIsNotNone(visualizer)
        self.assertTrue(hasattr(visualizer, 'add_candle'))
        self.assertTrue(hasattr(visualizer, 'add_signal'))
        self.assertTrue(hasattr(visualizer, 'add_order'))
    
    def test_visualizer_factory_returns_none_when_disabled(self):
        """Тест возврата None когда визуализация отключена"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=False
        )
        visualizer = self.factory.create_visualizer(config)
        self.assertIsNone(visualizer)
    
    def test_mock_visualizer_interface(self):
        """Тест мок визуализатора"""
        visualizer = MockTradingVisualizer()
        
        # Проверяем интерфейс
        self.assertTrue(hasattr(visualizer, 'add_candle'))
        self.assertTrue(hasattr(visualizer, 'add_signal'))
        self.assertTrue(hasattr(visualizer, 'add_order'))
        self.assertTrue(hasattr(visualizer, 'update_portfolio'))
        self.assertTrue(hasattr(visualizer, 'update_market_status'))
        self.assertTrue(hasattr(visualizer, 'start'))
        self.assertTrue(hasattr(visualizer, 'stop'))
        self.assertTrue(hasattr(visualizer, 'is_running'))
    
    def test_mock_visualizer_data_storage(self):
        """Тест хранения данных в мок визуализаторе"""
        visualizer = MockTradingVisualizer()
        
        # Тестовые данные
        candle_data = {
            'time': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000
        }
        
        signal_data = {
            'time': datetime.now(),
            'type': 'buy',
            'price': 102.0,
            'reason': 'test signal'
        }
        
        order_data = {
            'time': datetime.now(),
            'type': 'buy',
            'price': 102.0,
            'quantity': 10
        }
        
        # Добавляем данные
        asyncio.run(visualizer.add_candle(candle_data))
        asyncio.run(visualizer.add_signal(signal_data))
        asyncio.run(visualizer.add_order(order_data))
        
        # Проверяем, что данные сохранились
        self.assertEqual(len(visualizer.candles), 1)
        self.assertEqual(len(visualizer.signals), 1)
        self.assertEqual(len(visualizer.orders), 1)
        
        self.assertEqual(visualizer.candles[0], candle_data)
        self.assertEqual(visualizer.signals[0], signal_data)
        self.assertEqual(visualizer.orders[0], order_data)
    
    def test_mock_visualizer_lifecycle(self):
        """Тест жизненного цикла мок визуализатора"""
        visualizer = MockTradingVisualizer()
        
        # Проверяем начальное состояние
        self.assertFalse(visualizer.is_running())
        
        # Запускаем
        asyncio.run(visualizer.start())
        self.assertTrue(visualizer.is_running())
        
        # Останавливаем
        asyncio.run(visualizer.stop())
        self.assertFalse(visualizer.is_running())
    
    def test_visualizer_factory_with_mock(self):
        """Тест фабрики с мок визуализатором"""
        # Создаем мок визуализатор
        mock_visualizer = self.factory.create_mock_visualizer()
        
        self.assertIsNotNone(mock_visualizer)
        self.assertIsInstance(mock_visualizer, MockTradingVisualizer)
        
        # Проверяем, что можно добавить данные
        candle_data = {
            'time': datetime.now(),
            'open': 100.0,
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000
        }
        
        asyncio.run(mock_visualizer.add_candle(candle_data))
        self.assertEqual(len(mock_visualizer.candles), 1)


if __name__ == '__main__':
    unittest.main()
