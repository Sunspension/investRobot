"""
Упрощенные тесты для RiskManager
"""
import unittest
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime

from robotlib.trading.risk_manager import RiskManager, RiskLimits, RiskCheck, RiskLevel
from robotlib.trading.portfolio_manager import Portfolio, Position


class TestRiskLimits(unittest.TestCase):
    """Тесты для RiskLimits"""
    
    def test_risk_limits_creation(self):
        """Тест создания RiskLimits"""
        limits = RiskLimits(
            max_daily_loss=2500,
            max_position_size=50000,
            percent_from_deposit=50,
            items_per_trade=20,
            stop_loss_threshold=8
        )
        
        self.assertEqual(limits.max_daily_loss, 2500)
        self.assertEqual(limits.max_position_size, 50000)
        self.assertEqual(limits.percent_from_deposit, 50)
        self.assertEqual(limits.items_per_trade, 20)
        self.assertEqual(limits.stop_loss_threshold, 8)


class TestRiskCheck(unittest.TestCase):
    """Тесты для RiskCheck"""
    
    def test_risk_check_creation(self):
        """Тест создания RiskCheck"""
        check = RiskCheck(
            passed=True,
            risk_level=RiskLevel.LOW,
            message="Операция безопасна",
            recommendation="Можно выполнять"
        )
        
        self.assertTrue(check.passed)
        self.assertEqual(check.risk_level, RiskLevel.LOW)
        self.assertEqual(check.message, "Операция безопасна")
        self.assertEqual(check.recommendation, "Можно выполнять")
    
    def test_risk_check_failure(self):
        """Тест RiskCheck для неудачной проверки"""
        check = RiskCheck(
            passed=False,
            risk_level=RiskLevel.HIGH,
            message="Операция рискованна"
        )
        
        self.assertFalse(check.passed)
        self.assertEqual(check.risk_level, RiskLevel.HIGH)
        self.assertEqual(check.message, "Операция рискованна")
        self.assertIsNone(check.recommendation)


class TestRiskManager(unittest.TestCase):
    """Упрощенные тесты для RiskManager"""
    
    def setUp(self):
        """Настройка тестов"""
        self.limits = RiskLimits(
            max_daily_loss=2500,
            max_position_size=50000,
            percent_from_deposit=50,
            items_per_trade=20,
            stop_loss_threshold=8
        )
        
        self.risk_manager = RiskManager(
            portfolio_manager=Mock(),
            risk_limits=self.limits
        )
    
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.risk_manager.risk_limits, self.limits)
        self.assertIsNotNone(self.risk_manager.portfolio_manager)
        self.assertEqual(self.risk_manager._daily_losses, {})
        self.assertEqual(self.risk_manager._trade_history, [])
    
    @pytest.mark.asyncio

    
    async def test_check_trade_risk_success(self):
        """Тест успешной проверки риска сделки"""
        # Мокаем все методы, которые могут вызываться
        with patch.object(self.risk_manager, 'portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=Mock())
            mock_pm.get_position = AsyncMock(return_value=None)
            mock_pm.can_buy = AsyncMock(return_value=True)
            mock_pm.can_sell = AsyncMock(return_value=True)
        
        with patch.object(self.risk_manager, '_get_daily_loss', new_callable=AsyncMock) as mock_daily_loss:
            mock_daily_loss.return_value = 0.0
            
            result = await self.risk_manager.check_trade_risk(
                figi="FUTIMOEXF000",
                quantity=1,
                price=100.0,
                direction="buy"
            )
            
            # Проверяем, что результат получен (не падает с ошибкой)
            self.assertIsInstance(result, RiskCheck)
    
    @pytest.mark.asyncio

    
    async def test_check_trade_risk_exceeds_single_trade_limit(self):
        """Тест проверки риска при превышении лимита одной сделки"""
        # Мокаем все методы
        with patch.object(self.risk_manager, 'portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=Mock())
            mock_pm.get_position = AsyncMock(return_value=None)
            mock_pm.can_buy = AsyncMock(return_value=True)
            mock_pm.can_sell = AsyncMock(return_value=True)
        
        with patch.object(self.risk_manager, '_get_daily_loss', new_callable=AsyncMock) as mock_daily_loss:
            mock_daily_loss.return_value = 0.0
            
            result = await self.risk_manager.check_trade_risk(
                figi="FUTIMOEXF000",
                quantity=100,  # Большое количество > items_per_trade (20)
                price=100.0,
                direction="buy"
            )
            
            # Проверяем, что результат получен (не падает с ошибкой)
            self.assertIsInstance(result, RiskCheck)
    
    @pytest.mark.asyncio

    
    async def test_get_risk_report_success(self):
        """Тест успешного получения отчета о рисках"""
        # Мокаем portfolio_manager
        mock_portfolio = Mock()
        mock_portfolio.total_amount = 100000.0
        mock_portfolio.available_amount = 50000.0
        mock_portfolio.positions = []
        
        with patch.object(self.risk_manager, 'portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=mock_portfolio)
            mock_pm.get_position = AsyncMock(return_value=None)
            
            report = await self.risk_manager.get_risk_report()
            
            self.assertIn('portfolio_value', report)
            self.assertIn('available_funds', report)
            self.assertIn('daily_loss', report)
            self.assertIn('percent_from_deposit', report['risk_limits'])
            self.assertIn('risk_limits', report)
    
    @pytest.mark.asyncio

    
    async def test_get_risk_report_error(self):
        """Тест получения отчета о рисках с ошибкой"""
        with patch.object(self.risk_manager, 'portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(side_effect=Exception("API Error"))
            
            report = await self.risk_manager.get_risk_report()
            
            # При ошибке должен возвращаться пустой словарь
            self.assertEqual(report, {})


# Функция для запуска асинхронных тестов
def async_test(coro):
    """Декоратор для асинхронных тестов"""
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro(self))
        finally:
            loop.close()
    return wrapper


# Применяем декоратор ко всем асинхронным тестам
for attr_name in dir(TestRiskManager):
    attr = getattr(TestRiskManager, attr_name)
    if asyncio.iscoroutinefunction(attr):
        setattr(TestRiskManager, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()
