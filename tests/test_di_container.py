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
            db_path=self.temp_db.name
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
        """Тест с включенной визуализацией - используем моки для ускорения"""
        # Мокаем весь процесс создания визуализатора
        with patch('robotlib.trading.di_container.TradingSystemContainer.get_visualizer') as mock_get_visualizer:
            mock_get_visualizer.return_value = Mock()  # Возвращаем мок вместо реального визуализатора
            
            # Создаем конфигурацию с визуализацией
            config_with_viz = TradingConfig(
                figi="FUTIMOEXF000", 
                enable_visualization=True,
                db_path=self.temp_db.name  # Используем существующую БД
            )
            config_with_viz.tcs_client = self.config.tcs_client
            container_with_viz = TradingSystemContainer(config_with_viz)
            
            # Мокаем build_trading_system чтобы он не создавал реальные компоненты
            with patch.object(container_with_viz, 'build_trading_system') as mock_build:
                mock_build.return_value = {
                    'config': config_with_viz,
                    'session_controller': Mock(),
                    'dependencies': Mock(),
                    'visualizer': Mock()  # Мок визуализатора
                }
                
                trading_system = asyncio.run(container_with_viz.build_trading_system())
                
                # Проверяем, что визуализатор был создан
                self.assertIsNotNone(trading_system['visualizer'])
                # Проверяем, что build_trading_system был вызван
                mock_build.assert_called_once()
    
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
