"""
Исправленные тесты для стратегий торговли
"""
import sys
from pathlib import Path
import unittest
import pytest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
from datetime import datetime

# Добавляем корневую директорию проекта в sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from tests.mocks.position_sizer_dummy import DummySizer
from robotlib.signal_manager import Signal
from robotlib.trading.portfolio_manager import Portfolio, Position
from robotlib.utils.money import Money


class RaisingSizer:
    async def calculate_position_size(self, signal, current_position: int, figi: str = "FUTIMOEXF000") -> int:
        raise Exception("API Error")


class TestLongStrategy(unittest.TestCase):
    """Тесты для LongStrategy"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_risk_manager = Mock()
        self.mock_risk_manager.risk_limits.percent_from_deposit = 50.0
        self.mock_risk_manager.risk_limits.items_per_trade = 20
        self.mock_portfolio_manager = Mock()
        self.strategy = LongStrategy(
            risk_manager=self.mock_risk_manager,
            portfolio_manager=self.mock_portfolio_manager,
            position_sizing_service=DummySizer(),
        )
    
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.strategy._portfolio_manager, self.mock_portfolio_manager)
        self.assertEqual(self.strategy.strategy_name, "LongStrategy")
    
    @pytest.mark.asyncio

    
    async def test_execute_no_signal(self):
        """Тест выполнения без сигнала"""
        # Создаем пустой сигнал вместо None
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = False
        mock_signal.histogram = 0.0
        mock_signal.macd = 0.0
        mock_signal.signal = 0.0
        mock_signal.macd_prev = None
        mock_signal.signal_prev = None
        mock_signal.candle = Mock()
        mock_signal.candle.close = 100.0
        
        result = await self.strategy.execute(mock_signal)
        
        self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_execute_buy_signal_success(self):
        """Тест успешного выполнения сигнала на покупку"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0  # Правильное значение для Money
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = True
        mock_signal.peak_detected = False
        mock_signal.histogram = -0.5
        mock_signal.macd = -0.3
        mock_signal.signal = -0.2
        mock_signal.macd_prev = -0.4
        mock_signal.signal_prev = -0.1
        mock_signal.candle = mock_candle
        
        # Мокаем портфель
        mock_portfolio = Mock()
        mock_portfolio.total_amount = 100000.0
        mock_portfolio.available_amount = 50000.0
        mock_portfolio.positions = []
        
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=mock_portfolio)
            mock_pm.get_deposit = AsyncMock(return_value=100000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy.execute(mock_signal)
            
            self.assertIsNotNone(result)
            self.assertIsInstance(result, list)
    
    @pytest.mark.asyncio

    
    async def test_execute_sell_signal_success(self):
        """Тест успешного выполнения сигнала на продажу"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = True
        mock_signal.histogram = 0.5
        mock_signal.macd = 0.3
        mock_signal.signal = 0.2
        mock_signal.macd_prev = 0.4
        mock_signal.signal_prev = 0.1
        mock_signal.candle = mock_candle
        
        # Устанавливаем позицию для продажи
        self.strategy._position = 5
        self.strategy._cost_basis = 95.0
        
        result = await self.strategy.execute(mock_signal)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
    
    @pytest.mark.asyncio

    
    async def test_execute_insufficient_funds(self):
        """Тест выполнения при недостатке средств"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = True
        mock_signal.peak_detected = False
        mock_signal.histogram = -0.5
        mock_signal.macd = -0.3
        mock_signal.signal = -0.2
        mock_signal.macd_prev = -0.4
        mock_signal.signal_prev = -0.1
        mock_signal.candle = mock_candle
        
        # Мокаем портфель с недостатком средств
        mock_portfolio = Mock()
        mock_portfolio.total_amount = 1000.0  # Мало средств
        mock_portfolio.available_amount = 500.0
        mock_portfolio.positions = []
        
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=mock_portfolio)
            mock_pm.get_deposit = AsyncMock(return_value=1000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy.execute(mock_signal)
            
            # Должен вернуть пустой список при недостатке средств
            self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_execute_no_position_to_sell(self):
        """Тест выполнения сигнала на продажу без позиции"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = True
        mock_signal.histogram = 0.5
        mock_signal.macd = 0.3
        mock_signal.signal = 0.2
        mock_signal.macd_prev = 0.4
        mock_signal.signal_prev = 0.1
        mock_signal.candle = mock_candle
        
        # Устанавливаем нулевую позицию
        self.strategy._position = 0
        
        result = await self.strategy.execute(mock_signal)
        
        # Должен вернуть пустой список, так как нет позиции для продажи
        self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_items_to_buy_calculation(self):
        """Тест расчета количества для покупки"""
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_deposit = AsyncMock(return_value=100000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy._items_to_buy(100.0)
            
            # Проверяем, что результат больше 0
            self.assertGreater(result, 0)
    
    @pytest.mark.asyncio

    
    async def test_items_to_buy_api_error(self):
        """Тест расчета количества при ошибке API"""
        # Подменяем сайзер на выбрасывающий исключение
        self.strategy._position_sizing_service = RaisingSizer()
        with self.assertRaises(Exception) as context:
            await self.strategy._items_to_buy(100.0)
        self.assertIn("API Error", str(context.exception))


class TestShortStrategy(unittest.TestCase):
    """Тесты для ShortStrategy"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_risk_manager = Mock()
        self.mock_risk_manager.risk_limits.percent_from_deposit = 50.0
        self.mock_risk_manager.risk_limits.items_per_trade = 20
        self.mock_portfolio_manager = Mock()
        self.strategy = ShortStrategy(
            risk_manager=self.mock_risk_manager,
            portfolio_manager=self.mock_portfolio_manager,
            position_sizing_service=DummySizer(),
        )
    
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.strategy._portfolio_manager, self.mock_portfolio_manager)
        self.assertEqual(self.strategy.strategy_name, "ShortStrategy")
    
    @pytest.mark.asyncio

    
    async def test_execute_no_signal(self):
        """Тест выполнения без сигнала"""
        # Создаем пустой сигнал вместо None
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = False
        mock_signal.histogram = 0.0
        mock_signal.macd = 0.0
        mock_signal.signal = 0.0
        mock_signal.macd_prev = None
        mock_signal.signal_prev = None
        mock_signal.candle = Mock()
        mock_signal.candle.close = 100.0
        
        result = await self.strategy.execute(mock_signal)
        
        self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_execute_sell_short_signal_success(self):
        """Тест успешного выполнения сигнала на продажу в шорт"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = True
        mock_signal.histogram = 0.5
        mock_signal.macd = 0.3
        mock_signal.signal = 0.2
        mock_signal.macd_prev = 0.4
        mock_signal.signal_prev = 0.1
        mock_signal.candle = mock_candle
        
        # Мокаем портфель
        mock_portfolio = Mock()
        mock_portfolio.total_amount = 100000.0
        mock_portfolio.available_amount = 50000.0
        mock_portfolio.positions = []
        
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=mock_portfolio)
            mock_pm.get_deposit = AsyncMock(return_value=100000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy.execute(mock_signal)
            
            self.assertIsNotNone(result)
            self.assertIsInstance(result, list)
    
    @pytest.mark.asyncio

    
    async def test_execute_buy_short_signal_success(self):
        """Тест успешного выполнения сигнала на покупку для закрытия шорта"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = True
        mock_signal.peak_detected = False
        mock_signal.histogram = -0.5
        mock_signal.macd = -0.3
        mock_signal.signal = -0.2
        mock_signal.macd_prev = -0.4
        mock_signal.signal_prev = -0.1
        mock_signal.candle = mock_candle
        
        # Устанавливаем короткую позицию для закрытия
        self.strategy._position = -5
        self.strategy._cost_basis = 105.0
        
        result = await self.strategy.execute(mock_signal)
        
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
    
    @pytest.mark.asyncio

    
    async def test_execute_insufficient_funds(self):
        """Тест выполнения при недостатке средств"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = False
        mock_signal.peak_detected = True
        mock_signal.histogram = 0.5
        mock_signal.macd = 0.3
        mock_signal.signal = 0.2
        mock_signal.macd_prev = 0.4
        mock_signal.signal_prev = 0.1
        mock_signal.candle = mock_candle
        
        # Мокаем портфель с недостатком средств
        mock_portfolio = Mock()
        mock_portfolio.total_amount = 1000.0  # Мало средств
        mock_portfolio.available_amount = 500.0
        mock_portfolio.positions = []
        
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_portfolio = AsyncMock(return_value=mock_portfolio)
            mock_pm.get_deposit = AsyncMock(return_value=1000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy.execute(mock_signal)
            
            # Должен вернуть пустой список при недостатке средств
            self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_execute_no_short_position_to_close(self):
        """Тест выполнения сигнала на закрытие шорта без позиции"""
        # Создаем мок свечи
        mock_candle = Mock()
        mock_candle.close = 100.0
        
        # Создаем мок сигнала
        mock_signal = Mock()
        mock_signal.trough_detected = True
        mock_signal.peak_detected = False
        mock_signal.histogram = -0.5
        mock_signal.macd = -0.3
        mock_signal.signal = -0.2
        mock_signal.macd_prev = -0.4
        mock_signal.signal_prev = -0.1
        mock_signal.candle = mock_candle
        
        # Устанавливаем нулевую позицию
        self.strategy._position = 0
        
        result = await self.strategy.execute(mock_signal)
        
        # Должен вернуть пустой список, так как нет позиции для закрытия
        self.assertEqual(result, [])
    
    @pytest.mark.asyncio

    
    async def test_items_to_sell_short_calculation(self):
        """Тест расчета количества для продажи в шорт"""
        with patch.object(self.strategy, '_portfolio_manager') as mock_pm:
            mock_pm.get_deposit = AsyncMock(return_value=100000.0)
            mock_pm.get_guarantee_deposit = AsyncMock(return_value=1700.0)
            
            result = await self.strategy._items_to_sell_short(100.0)
            
            # Проверяем, что результат больше 0
            self.assertGreater(result, 0)
    
    @pytest.mark.asyncio

    
    async def test_items_to_sell_short_api_error(self):
        """Тест расчета количества при ошибке API"""
        # Подменяем сайзер на выбрасывающий исключение
        self.strategy._position_sizing_service = RaisingSizer()
        with self.assertRaises(Exception) as context:
            await self.strategy._items_to_sell_short(100.0)
        self.assertIn("API Error", str(context.exception))


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
for attr_name in dir(TestLongStrategy):
    attr = getattr(TestLongStrategy, attr_name)
    if asyncio.iscoroutinefunction(attr):
        setattr(TestLongStrategy, attr_name, async_test(attr))

for attr_name in dir(TestShortStrategy):
    attr = getattr(TestShortStrategy, attr_name)
    if asyncio.iscoroutinefunction(attr):
        setattr(TestShortStrategy, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()
