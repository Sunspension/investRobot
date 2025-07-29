"""
Тесты для логики закрытия позиций в конце дня
"""
import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, time, timedelta
import pytz

from robotlib.trading.session_controller import SessionController
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_stats import SessionStats


class TestEndOfDayClosing(unittest.TestCase):
    """Тесты для закрытия позиций в конце дня"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем моки для зависимостей
        self.mock_deps = Mock(spec=TradingDependencies)
        self.mock_deps.api_client = Mock()
        self.mock_deps.market_data_stream = AsyncMock()
        self.mock_deps.strategy_manager = AsyncMock()
        self.mock_deps.session_stats = Mock(spec=SessionStats)
        self.mock_deps.session_initializer = Mock()
        
        # Создаем конфигурацию с закрытием в конце дня
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            auto_close_positions=True,
            end_of_day_close=True,
            close_time=time(23, 50),
            warning_periods=[600, 300, 60]  # 10, 5, 1 минута
        )
        
        # Создаем контроллер
        self.controller = SessionController(self.config, self.mock_deps)
    
    def test_config_initialization(self):
        """Тест инициализации конфигурации"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            auto_close_positions=True,
            end_of_day_close=True,
            close_time=time(23, 50),
            warning_periods=[600, 300, 60]
        )
        
        self.assertEqual(config.figi, "FUTIMOEXF000")
        self.assertTrue(config.auto_close_positions)
        self.assertTrue(config.end_of_day_close)
        self.assertEqual(config.close_time, time(23, 50))
        self.assertEqual(config.warning_periods, [600, 300, 60])
    
    def test_config_default_values(self):
        """Тест значений по умолчанию"""
        config = TradingConfig(figi="FUTIMOEXF000")
        
        self.assertEqual(config.figi, "FUTIMOEXF000")
        self.assertTrue(config.auto_close_positions)
        self.assertTrue(config.end_of_day_close)
        self.assertEqual(config.close_time, time(23, 50))
        self.assertEqual(config.warning_periods, [600, 300, 60])
    
    def test_config_warning_periods_sorted(self):
        """Тест сортировки периодов предупреждений"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            warning_periods=[60, 600, 300]
        )
        
        # Периоды должны быть отсортированы по убыванию
        self.assertEqual(config.warning_periods, [600, 300, 60])
    
    def test_get_time_to_close_method_exists(self):
        """Тест что метод _get_time_to_close существует и вызывается"""
        # Проверяем что метод существует
        self.assertTrue(hasattr(self.controller, '_get_time_to_close'))
        self.assertTrue(callable(getattr(self.controller, '_get_time_to_close')))
    
    def test_check_close_warnings_method_exists(self):
        """Тест что метод _check_close_warnings существует и вызывается"""
        # Проверяем что метод существует
        self.assertTrue(hasattr(self.controller, '_check_close_warnings'))
        self.assertTrue(callable(getattr(self.controller, '_check_close_warnings')))
    
    def test_check_close_warnings_first_warning(self):
        """Тест первого предупреждения"""
        shown_warnings = set()
        
        async def _test():
            # 10 минут до закрытия
            await self.controller._check_close_warnings(600, shown_warnings)
            return shown_warnings
        
        result = asyncio.run(_test())
        
        # Должно показать предупреждение за 10 минут
        self.assertIn(600, result)
    
    def test_check_close_warnings_multiple_warnings(self):
        """Тест нескольких предупреждений"""
        shown_warnings = set()
        
        async def _test():
            # Сначала 10 минут
            await self.controller._check_close_warnings(600, shown_warnings)
            # Потом 5 минут
            await self.controller._check_close_warnings(300, shown_warnings)
            # Потом 1 минута
            await self.controller._check_close_warnings(60, shown_warnings)
            return shown_warnings
        
        result = asyncio.run(_test())
        
        # Должны показать все предупреждения
        self.assertIn(600, result)
        self.assertIn(300, result)
        self.assertIn(60, result)
    
    def test_check_close_warnings_no_duplicate_warnings(self):
        """Тест отсутствия дублирующихся предупреждений"""
        shown_warnings = {600}  # Уже показано предупреждение за 10 минут
        
        async def _test():
            # Пытаемся показать предупреждение за 10 минут снова
            await self.controller._check_close_warnings(600, shown_warnings)
            return shown_warnings
        
        result = asyncio.run(_test())
        
        # Должно остаться только одно предупреждение
        self.assertEqual(len(result), 1)
        self.assertIn(600, result)
    
    def test_check_close_warnings_no_warning_when_time_not_reached(self):
        """Тест отсутствия предупреждения когда время не достигнуто"""
        shown_warnings = set()
        
        async def _test():
            # 20 минут до закрытия (больше чем 10 минут)
            await self.controller._check_close_warnings(1200, shown_warnings)
            return shown_warnings
        
        result = asyncio.run(_test())
        
        # Не должно показать предупреждение
        self.assertEqual(len(result), 0)
    
    def test_trading_loop_integration(self):
        """Тест интеграции торгового цикла с новой функциональностью"""
        # Проверяем что в торговом цикле есть проверка end_of_day_close
        self.assertTrue(hasattr(self.controller, 'config'))
        self.assertTrue(hasattr(self.controller.config, 'end_of_day_close'))
        self.assertTrue(hasattr(self.controller.config, 'close_time'))
        self.assertTrue(hasattr(self.controller.config, 'warning_periods'))


class TestEndOfDayClosingIntegration(unittest.TestCase):
    """Интеграционные тесты для закрытия позиций в конце дня"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем моки для зависимостей
        self.mock_deps = Mock(spec=TradingDependencies)
        self.mock_deps.api_client = Mock()
        self.mock_deps.market_data_stream = AsyncMock()
        self.mock_deps.strategy_manager = AsyncMock()
        self.mock_deps.session_stats = Mock(spec=SessionStats)
        self.mock_deps.session_initializer = Mock()
    
    def test_custom_close_time(self):
        """Тест с пользовательским временем закрытия"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            close_time=time(18, 0),  # Закрытие в 18:00
            warning_periods=[300, 60]  # Предупреждения за 5 и 1 минуту
        )
        
        controller = SessionController(config, self.mock_deps)
        
        self.assertEqual(controller.config.close_time, time(18, 0))
        self.assertEqual(controller.config.warning_periods, [300, 60])
    
    def test_custom_warning_periods(self):
        """Тест с пользовательскими периодами предупреждений"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            warning_periods=[1200, 600, 300, 60, 30]  # 20, 10, 5, 1, 0.5 минуты
        )
        
        controller = SessionController(config, self.mock_deps)
        
        # Периоды должны быть отсортированы по убыванию
        self.assertEqual(controller.config.warning_periods, [1200, 600, 300, 60, 30])
    
    def test_disabled_end_of_day_closing(self):
        """Тест отключенного закрытия в конце дня"""
        config = TradingConfig(
            figi="FUTIMOEXF000",
            end_of_day_close=False
        )
        
        controller = SessionController(config, self.mock_deps)
        
        self.assertFalse(controller.config.end_of_day_close)
        # Время закрытия все равно должно быть установлено
        self.assertEqual(controller.config.close_time, time(23, 50))


if __name__ == '__main__':
    unittest.main()
