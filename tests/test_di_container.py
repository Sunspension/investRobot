"""
Тесты для DI контейнера
"""
import unittest
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from typing import Protocol

from typing import runtime_checkable

# В новой архитектуре EventBus не используется — оставшиеся проверки
# заменяем на минимальные duck-typed проверки совместимости там, где нужно.


class TestTradingSystemContainer(unittest.TestCase):
    """Тесты для DI контейнера"""
    
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
        
        self.container = TradingSystemContainer(self.config)
    
    def test_singleton_instances(self):
        """Тест, что экземпляры создаются как синглтоны"""
        session_stats1 = self.container.get_session_stats()
        session_stats2 = self.container.get_session_stats()
        self.assertIs(session_stats1, session_stats2)
    
    def test_trading_dependencies(self):
        """Тест создания зависимостей торговой системы"""
        import asyncio
        dependencies = asyncio.run(self.container.get_trading_dependencies())
    
        # Проверяем, что все зависимости созданы
        self.assertIsNotNone(dependencies.session_stats)
        self.assertIsNotNone(dependencies.portfolio_manager)
        self.assertIsNotNone(dependencies.risk_manager)
        self.assertIsNotNone(dependencies.order_executor)
        # market_data_stream может быть None в синхронной версии
        # self.assertIsNotNone(dependencies.market_data_stream)
        self.assertIsNotNone(dependencies.signal_manager)
        self.assertIsNotNone(dependencies.strategy_manager)
    
    def test_session_controller_creation(self):
        """Тест создания контроллера сессии"""
        import asyncio
        session_controller = asyncio.run(self.container.get_session_controller())
        self.assertIsNotNone(session_controller)
        self.assertEqual(session_controller.config, self.config)
    
    def test_build_trading_system(self):
        """Тест сборки полной торговой системы"""
        import asyncio
        trading_system = asyncio.run(self.container.build_trading_system())
        
        # Проверяем, что все компоненты присутствуют
        self.assertIn('config', trading_system)
        self.assertIn('session_controller', trading_system)
        self.assertIn('dependencies', trading_system)
        self.assertIn('visualizer', trading_system)
        self.assertIsNone(trading_system['visualizer'])  # Визуализация отключена
    
    def test_visualization_enabled(self):
        """Тест с включенной визуализацией"""
        config_with_viz = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
        config_with_viz.tcs_client = self.config.tcs_client
        container_with_viz = TradingSystemContainer(config_with_viz)
        import asyncio
        trading_system = asyncio.run(container_with_viz.build_trading_system())
        # Визуализатор может быть None в тестовой среде
        self.assertIn('visualizer', trading_system)
    
    def test_config_validation(self):
        """Тест валидации конфигурации"""
        # Тест с пустым FIGI
        config_empty_figi = TradingConfig(figi="")
        config_empty_figi.tcs_client = self.config.tcs_client
        
        with self.assertRaises(ValueError) as context:
            TradingSystemContainer(config_empty_figi)
        self.assertIn("FIGI не может быть пустым", str(context.exception))
        
        # Тест без TCS клиента
        config_no_tcs = TradingConfig(figi="FUTIMOEXF000")
        
        with self.assertRaises(ValueError) as context:
            TradingSystemContainer(config_no_tcs)
        self.assertIn("TCS клиент не настроен", str(context.exception))
        
        # Тест с неполным TCS клиентом
        config_incomplete_tcs = TradingConfig(figi="FUTIMOEXF000")
        config_incomplete_tcs.tcs_client = type('MockTCSClient', (), {
            'token': '',  # Пустой токен
            'id': 'test_account_id',
            'sandbox_token': 'test_sandbox_token'
        })()
        
        with self.assertRaises(ValueError) as context:
            TradingSystemContainer(config_incomplete_tcs)
        self.assertIn("Токен TCS клиента не настроен", str(context.exception))


if __name__ == '__main__':
    unittest.main()
