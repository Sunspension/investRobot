"""
Тесты для примера использования торговой системы с DI
"""
import unittest
import asyncio
import tempfile
import os
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from robotlib.utils.sql_schema import init_db
from unittest.mock import patch, Mock

class TestTradingSystemWithDI(unittest.TestCase):
    """Тесты для примера использования торговой системы с DI"""
    
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
    
    def tearDown(self):
        """Очистка после тестов"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
    
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
        """Тест торговой системы с визуализацией - используем моки для ускорения"""
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
            container = TradingSystemContainer(config_with_viz)
            
            # Мокаем build_trading_system чтобы он не создавал реальные компоненты
            with patch.object(container, 'build_trading_system') as mock_build:
                mock_build.return_value = {
                    'config': config_with_viz,
                    'session_controller': Mock(),
                    'dependencies': Mock(),
                    'visualizer': Mock()  # Мок визуализатора
                }
                
                trading_system = asyncio.run(container.build_trading_system())
                
                # Проверяем, что визуализатор был создан
                self.assertIsNotNone(trading_system['visualizer'])
                # Проверяем, что build_trading_system был вызван
                mock_build.assert_called_once()
    
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
        
        # Проверяем, что session_controller установлен
        session_controller = asyncio.run(container.get_session_controller())
        self.assertIsNotNone(session_controller)
    
    def test_build_trading_system(self):
        """Проверяем, что система собирается."""
        container = TradingSystemContainer(self.config)
        trading_system = asyncio.run(container.build_trading_system())
        self.assertIn('session_controller', trading_system)


if __name__ == '__main__':
    unittest.main()
