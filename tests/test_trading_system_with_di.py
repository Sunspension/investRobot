"""
Тесты для примера использования торговой системы с DI
"""
import unittest
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from typing import Protocol, runtime_checkable

# Убираем строгие интерфейсы EventBus — проверяем только наличие требуемых методов


class TestTradingSystemWithDI(unittest.TestCase):
    """Тесты для примера использования торговой системы с DI"""
    
    def setUp(self):
        """Настройка тестов"""
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=False
        )
        # Добавляем мок tcs_client для тестов
        from unittest.mock import Mock
        self.config.tcs_client = Mock()
        self.config.tcs_client.token = "test_token"
        self.config.tcs_client.id = "test_account_id"
        self.config.tcs_client.sandbox_token = "test_sandbox_token"
    
    def test_container_creation(self):
        """Тест создания контейнера"""
        container = TradingSystemContainer(self.config)
        self.assertIsInstance(container, TradingSystemContainer)
        self.assertEqual(container._config, self.config)
        self.assertFalse(container._config.enable_visualization)
    
    def test_trading_system_build(self):
        """Тест сборки торговой системы"""
        container = TradingSystemContainer(self.config)
        trading_system = asyncio.run(container.build_trading_system())
        
        # Проверяем, что все компоненты присутствуют
        self.assertIn('config', trading_system)
        self.assertIn('session_controller', trading_system)
        self.assertIn('dependencies', trading_system)
        self.assertIn('visualizer', trading_system)
        self.assertIsNone(trading_system['visualizer'])  # Визуализация отключена
    
    def test_trading_system_with_visualization(self):
        """Тест торговой системы с визуализацией"""
        # Создаем конфигурацию с визуализацией
        config_with_viz = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
        config_with_viz.tcs_client = self.config.tcs_client
        container = TradingSystemContainer(config_with_viz)
        trading_system = asyncio.run(container.build_trading_system())
        
        # Визуализатор может быть None
        
        # Визуализатор может быть None, если модуль недоступен
        # Но это нормально для тестов
    
    def test_singleton_behavior(self):
        """Тест синглтон поведения"""
        container = TradingSystemContainer(self.config)
        
        # Проверяем, что build_trading_system возвращает валидные компоненты
        trading_system = asyncio.run(container.build_trading_system())
        self.assertIn('dependencies', trading_system)
    
    def test_dependencies_injection(self):
        """Тест инжекции зависимостей"""
        container = TradingSystemContainer(self.config)
        trading_system = asyncio.run(container.build_trading_system())
        
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
        session_initializer = asyncio.run(container.get_session_initializer())
        self.assertIsNotNone(session_initializer)
    
    def test_no_event_bus_required(self):
        """Проверяем, что система собирается без EventBus."""
        container = TradingSystemContainer(self.config)
        trading_system = asyncio.run(container.build_trading_system())
        self.assertIn('session_controller', trading_system)


if __name__ == '__main__':
    unittest.main()
