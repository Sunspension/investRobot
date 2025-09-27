"""
Тесты для DI контейнера
"""
import unittest
import asyncio
import tempfile
import os
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.sql_schema import init_db
from typing import Protocol
from unittest.mock import patch, Mock

from typing import runtime_checkable

# В новой архитектуре EventBus не используется — оставшиеся проверки
# заменяем на минимальные duck-typed проверки совместимости там, где нужно.


class TestTradingSystemContainer(unittest.TestCase):
    """Тесты для DI контейнера"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем временную базу данных для тестов
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            enable_visualization=False,
            positions_db_path=self.temp_db.name,
            market_db_path=self.temp_db.name
        )
        # Добавляем мок tcs_client для тестов
        from unittest.mock import Mock
        self.config.tcs_client = Mock()
        self.config.tcs_client.token = "test_token"
        self.config.tcs_client.account_id = "test_account_id"
        self.config.tcs_client.sandbox_token = "test_sandbox_token"
        
        # Инициализируем базу данных
        import asyncio
        try:
            asyncio.run(init_db(self.temp_db.name))
        except RuntimeError:
            # Если event loop уже запущен, создаем новый
            import threading
            def init_db_sync():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(init_db(self.temp_db.name))
                finally:
                    loop.close()
            thread = threading.Thread(target=init_db_sync)
            thread.start()
            thread.join()
        
        self.container = TradingSystemContainer(self.config)
    
    def tearDown(self):
        """Очистка после тестов"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
    def test_singleton_instances(self):
        """Тест, что экземпляры создаются как синглтоны"""
        session_stats1 = self.container.get_session_stats()
        session_stats2 = self.container.get_session_stats()
        self.assertIs(session_stats1, session_stats2)
    
    def test_trading_dependencies(self):
        """Тест создания зависимостей торговой системы"""
        import asyncio
        
        # Мокаем ВСЕ зависимости - тестируем только контейнер
        with patch('robotlib.trading.di_container.TradingSystemContainer.get_api_client') as mock_api, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_portfolio_manager') as mock_portfolio, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_risk_manager') as mock_risk, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_order_executor') as mock_order, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_signal_manager') as mock_signal, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_strategy_manager') as mock_strategy, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_session_stats') as mock_stats, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_market_data_stream') as mock_stream, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_position_manager') as mock_position, \
             patch('robotlib.trading.di_container.TradingSystemContainer.get_data_manager') as mock_data, \
             patch('robotlib.trading.di_container.TradingSystemContainer._create_trading_bridge') as mock_bridge:
            
            # Настраиваем моки
            mock_api.return_value = Mock()
            mock_portfolio.return_value = Mock()
            mock_risk.return_value = Mock()
            mock_order.return_value = Mock()
            mock_signal.return_value = Mock()
            mock_strategy.return_value = Mock()
            mock_stats.return_value = Mock()
            mock_stream.return_value = Mock()
            mock_position.return_value = Mock()
            mock_data.return_value = Mock()
            mock_bridge.return_value = Mock()
            
            # Тестируем только метод контейнера
            dependencies = asyncio.run(self.container.get_trading_dependencies())
        
            # Проверяем, что контейнер правильно создал структуру зависимостей
            self.assertIsNotNone(dependencies.session_stats)
            self.assertIsNotNone(dependencies.portfolio_manager)
            self.assertIsNotNone(dependencies.risk_manager)
            self.assertIsNotNone(dependencies.order_executor)
            self.assertIsNotNone(dependencies.signal_manager)
            self.assertIsNotNone(dependencies.strategy_manager)
            self.assertIsNotNone(dependencies.market_data_stream)
            self.assertIsNotNone(dependencies.position_manager)
            self.assertIsNotNone(dependencies.data_manager)
            self.assertIsNotNone(dependencies.event_sink)
            
            # Проверяем, что методы были вызваны
            mock_stats.assert_called_once()
            mock_api.assert_called_once()
            mock_portfolio.assert_called_once()
            mock_risk.assert_called_once()
            mock_order.assert_called_once()
            mock_signal.assert_called_once()
            mock_strategy.assert_called_once()
            mock_stream.assert_called_once()
            mock_position.assert_called_once()
            mock_data.assert_called_once()
            mock_bridge.assert_called_once()
    
    def test_session_controller_creation(self):
        """Тест создания контроллера сессии"""
        import asyncio
        
        # Мокаем ВСЕ зависимости - тестируем только контейнер
        with patch('robotlib.trading.di_container.TradingSystemContainer.get_trading_dependencies') as mock_deps:
            mock_deps.return_value = Mock()
            
            # Тестируем только метод контейнера
            session_controller = asyncio.run(self.container.get_session_controller())
            
            # Проверяем, что контейнер правильно создал контроллер
            self.assertIsNotNone(session_controller)
            self.assertEqual(session_controller.config, self.config)
            
            # Проверяем, что метод был вызван
            mock_deps.assert_called_once()
    
    def test_build_trading_system(self):
        """Тест сборки полной торговой системы"""
        import asyncio
        
        # Мокаем ВСЕ зависимости - тестируем только контейнер
        with patch.object(self.container, 'get_session_controller') as mock_session_controller, \
             patch.object(self.container, 'get_trading_dependencies') as mock_dependencies, \
             patch.object(self.container, 'get_visualizer') as mock_visualizer:
            
            mock_session_controller.return_value = Mock()
            mock_dependencies.return_value = Mock()
            mock_visualizer.return_value = None  # Визуализация отключена
            
            # Тестируем только метод контейнера
            trading_system = asyncio.run(self.container.build_trading_system())
            
            # Проверяем, что контейнер правильно собрал систему
            self.assertIn('config', trading_system)
            self.assertIn('session_controller', trading_system)
            self.assertIn('dependencies', trading_system)
            self.assertIn('visualizer', trading_system)
            self.assertIsNone(trading_system['visualizer'])  # Визуализация отключена
            
            # Проверяем, что методы были вызваны
            mock_session_controller.assert_called_once()
            mock_dependencies.assert_called_once()
            mock_visualizer.assert_called_once()
    
    def test_visualization_enabled(self):
        """Тест с включенной визуализацией - мокаем все зависимости"""
        import asyncio
        
        # Создаем конфигурацию с визуализацией
        config_with_viz = TradingConfig(
            figi="FUTIMOEXF000", 
            enable_visualization=True,
            positions_db_path=self.temp_db.name,
            market_db_path=self.temp_db.name
        )
        config_with_viz.tcs_client = self.config.tcs_client
        container_with_viz = TradingSystemContainer(config_with_viz)
        
        # Мокаем ВСЕ зависимости - тестируем только контейнер
        with patch.object(container_with_viz, 'get_session_controller') as mock_session, \
             patch.object(container_with_viz, 'get_trading_dependencies') as mock_deps, \
             patch.object(container_with_viz, 'get_visualizer') as mock_viz:
            
            mock_session.return_value = Mock()
            mock_deps.return_value = Mock()
            mock_viz.return_value = Mock()  # Визуализатор включен
            
            # Тестируем только метод контейнера
            trading_system = asyncio.run(container_with_viz.build_trading_system())
            
            # Проверяем, что контейнер правильно собрал систему с визуализацией
            self.assertIn('config', trading_system)
            self.assertIn('session_controller', trading_system)
            self.assertIn('dependencies', trading_system)
            self.assertIn('visualizer', trading_system)
            self.assertIsNotNone(trading_system['visualizer'])  # Визуализатор включен
            
            # Проверяем, что методы были вызваны
            mock_session.assert_called_once()
            mock_deps.assert_called_once()
            mock_viz.assert_called_once()
    
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
            'account_id': 'test_account_id',
            'sandbox_token': 'test_sandbox_token'
        })()
        
        with self.assertRaises(ValueError) as context:
            TradingSystemContainer(config_incomplete_tcs)
        self.assertIn("Токен TCS клиента не настроен", str(context.exception))
    
    def test_trading_bridge_singleton(self):
        """Тест, что TradingToUIBridge создается как синглтон"""
        config_with_viz = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
        config_with_viz.tcs_client = self.config.tcs_client
        container_with_viz = TradingSystemContainer(config_with_viz)
        
        # Получаем bridge дважды
        bridge1 = container_with_viz.get_trading_bridge()
        bridge2 = container_with_viz.get_trading_bridge()
        
        # Проверяем, что это один и тот же объект (если визуализация включена)
        if bridge1 is not None and bridge2 is not None:
            self.assertIs(bridge1, bridge2)
            # Проверяем, что bridge сохранен в инстансах
            self.assertIn('trading_bridge', container_with_viz._instances)
            self.assertIs(container_with_viz._instances['trading_bridge'], bridge1)


if __name__ == '__main__':
    unittest.main()
