"""
Тесты для интерфейсов компонентов торговой сессии
"""
import unittest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from robotlib.trading.session_interfaces import (
    SessionStatsable, 
    SessionInitializable, 
    SessionControllable, 
    TradingSessionable
)
from tests.mocks import (
    MockSessionStats,
    MockSessionInitializer,
    MockSessionController,
    MockTradingSession
)


class TestSessionStatsable(unittest.TestCase):
    """Тесты для интерфейса ISessionStats"""
    
    def setUp(self):
        """Настройка тестов"""
        self.stats = MockSessionStats()
    
    def test_add_signal(self):
        """Тест добавления сигнала"""
        initial_count = self.stats.total_signals
        self.stats.add_signal()
        self.assertEqual(self.stats.total_signals, initial_count + 1)
    
    def test_add_successful_order(self):
        """Тест добавления успешного ордера"""
        initial_orders = self.stats.successful_orders
        initial_volume = self.stats.total_volume
        initial_profit = self.stats.total_profit
        
        self.stats.add_successful_order(100.0, 10.0)
        
        self.assertEqual(self.stats.successful_orders, initial_orders + 1)
        self.assertEqual(self.stats.total_volume, initial_volume + 100.0)
        self.assertEqual(self.stats.total_profit, initial_profit + 10.0)
    
    def test_add_failed_order(self):
        """Тест добавления неудачного ордера"""
        initial_count = self.stats.failed_orders
        self.stats.add_failed_order()
        self.assertEqual(self.stats.failed_orders, initial_count + 1)
    
    def test_update_balance(self):
        """Тест обновления баланса"""
        self.stats.update_balance(1000.0)
        self.assertEqual(self.stats.current_balance, 1000.0)
    
    def test_get_stats_dict(self):
        """Тест получения статистики"""
        stats_dict = self.stats.get_stats_dict()
        self.assertIsInstance(stats_dict, dict)
        self.assertIn('total_signals', stats_dict)
        self.assertIn('successful_orders', stats_dict)
        self.assertIn('failed_orders', stats_dict)
    
    def test_print_stats(self):
        """Тест вывода статистики"""
        # Должен выполняться без ошибок
        self.stats.print_stats()
    
    def test_finish_session(self):
        """Тест завершения сессии"""
        self.stats.finish_session()
        self.assertIsNotNone(self.stats.end_time)
    
    def test_properties(self):
        """Тест свойств интерфейса"""
        self.assertIsInstance(self.stats.start_time, datetime)
        self.assertIsInstance(self.stats.total_signals, int)
        self.assertIsInstance(self.stats.successful_orders, int)
        self.assertIsInstance(self.stats.failed_orders, int)
        self.assertIsInstance(self.stats.total_volume, float)
        self.assertIsInstance(self.stats.total_profit, float)
        self.assertIsInstance(self.stats.current_balance, float)


class TestSessionInitializable(unittest.TestCase):
    """Тесты для интерфейса ISessionInitializer"""
    
    def setUp(self):
        """Настройка тестов"""
        self.initializer = MockSessionInitializer()
    
    def test_initialize_components(self):
        """Тест инициализации компонентов"""
        async def _test():
            await self.initializer.initialize_components()
            self.assertTrue(self.initializer.initialize_components_called)
        asyncio.run(_test())
    
    def test_initialize_strategies(self):
        """Тест инициализации стратегий"""
        async def _test():
            await self.initializer.initialize_strategies()
            self.assertTrue(self.initializer.initialize_strategies_called)
        asyncio.run(_test())
    
    def test_initialize_data_streams(self):
        """Тест инициализации потоков данных"""
        async def _test():
            await self.initializer.initialize_data_streams()
            self.assertTrue(self.initializer.initialize_data_streams_called)
        asyncio.run(_test())
    
    def test_check_risk_limits(self):
        """Тест проверки лимитов риска"""
        async def _test():
            await self.initializer.check_risk_limits()
            self.assertTrue(self.initializer.check_risk_limits_called)
        asyncio.run(_test())


class TestSessionControllable(unittest.TestCase):
    """Тесты для интерфейса ISessionController"""
    
    def setUp(self):
        """Настройка тестов"""
        self.controller = MockSessionController()
    
    def test_start(self):
        """Тест запуска сессии"""
        async def _test():
            result = await self.controller.start()
            self.assertTrue(result)
            self.assertTrue(self.controller.start_called)
            self.assertTrue(self.controller.is_running)
            self.assertTrue(self.controller.is_initialized)
        asyncio.run(_test())
    
    def test_stop(self):
        """Тест остановки сессии"""
        async def _test():
            await self.controller.stop()
            self.assertTrue(self.controller.stop_called)
            self.assertFalse(self.controller.is_running)
        asyncio.run(_test())
    
    def test_run_trading_loop(self):
        """Тест торгового цикла"""
        async def _test():
            await self.controller.run_trading_loop()
            self.assertTrue(self.controller.run_trading_loop_called)
        asyncio.run(_test())
    
    def test_get_session_status(self):
        """Тест получения статуса сессии"""
        async def _test():
            status = await self.controller.get_session_status()
            self.assertIsInstance(status, dict)
            self.assertIn('is_running', status)
            self.assertIn('is_initialized', status)
            self.assertIn('stats', status)
        asyncio.run(_test())
    
    def test_properties(self):
        """Тест свойств интерфейса"""
        self.assertIsInstance(self.controller.is_running, bool)
        self.assertIsInstance(self.controller.is_initialized, bool)
        self.assertIsInstance(self.controller.stats, SessionStatsable)


class TestTradingSessionable(unittest.TestCase):
    """Тесты для интерфейса ITradingSession"""
    
    def setUp(self):
        """Настройка тестов"""
        self.session = MockTradingSession()
    
    def test_start(self):
        """Тест запуска сессии"""
        async def _test():
            result = await self.session.start()
            self.assertTrue(result)
            self.assertTrue(self.session.start_called)
        asyncio.run(_test())
    
    def test_stop(self):
        """Тест остановки сессии"""
        async def _test():
            await self.session.stop()
            self.assertTrue(self.session.stop_called)
        asyncio.run(_test())
    
    def test_run_trading_loop(self):
        """Тест торгового цикла"""
        async def _test():
            await self.session.run_trading_loop()
            self.assertTrue(self.session.run_trading_loop_called)
        asyncio.run(_test())
    
    def test_get_stats(self):
        """Тест получения статистики"""
        stats = self.session.get_stats()
        self.assertIsInstance(stats, dict)
    
    def test_print_stats(self):
        """Тест вывода статистики"""
        # Должен выполняться без ошибок
        self.session.print_stats()
    
    def test_execute_signal(self):
        """Тест выполнения сигнала"""
        async def _test():
            signal = MagicMock()
            await self.session.execute_signal(signal)
            self.assertTrue(self.session.execute_signal_called)
        asyncio.run(_test())
    
    def test_get_session_status(self):
        """Тест получения статуса сессии"""
        async def _test():
            status = await self.session.get_session_status()
            self.assertIsInstance(status, dict)
        asyncio.run(_test())
    
    def test_close_all_positions(self):
        """Тест закрытия всех позиций"""
        async def _test():
            await self.session.close_all_positions()
            self.assertTrue(self.session.close_all_positions_called)
        asyncio.run(_test())


class TestInterfaceCompatibility(unittest.TestCase):
    """Тесты совместимости интерфейсов"""
    
    def test_session_stats_implements_interface(self):
        """Тест что SessionStats реализует ISessionStats"""
        from robotlib.trading.session_stats import SessionStats
        stats = SessionStats()
        self.assertIsInstance(stats, SessionStatsable)
    
    def test_session_controller_implements_interface(self):
        """Тест что SessionController реализует ISessionController"""
        from robotlib.trading.session_controller import SessionController
        from robotlib.trading.interfaces import TradingDependencies
        from robotlib.trading.trading_config import TradingConfig
        
        # Создаем моки для зависимостей
        mock_deps = MagicMock(spec=TradingDependencies)
        mock_deps.session_stats = MagicMock()
        mock_deps.session_initializer = MagicMock()
        mock_deps.strategy_manager = MagicMock()
        mock_config = MagicMock(spec=TradingConfig)
        
        controller = SessionController(mock_config, mock_deps)
        self.assertIsInstance(controller, SessionControllable)
    
    def test_trading_session_implements_interface(self):
        """Тест что TradingSession реализует ITradingSession"""
        from robotlib.trading.trading_session import TradingSession
        from robotlib.trading.interfaces import TradingDependencies
        from robotlib.trading.trading_config import TradingConfig
        
        # Создаем моки для зависимостей
        mock_deps = MagicMock(spec=TradingDependencies)
        mock_deps.session_stats = MagicMock()
        mock_deps.session_initializer = MagicMock()
        mock_deps.strategy_manager = MagicMock()
        mock_config = MagicMock(spec=TradingConfig)
        
        session = TradingSession(mock_config, mock_deps)
        self.assertIsInstance(session, TradingSessionable)


if __name__ == '__main__':
    unittest.main()
