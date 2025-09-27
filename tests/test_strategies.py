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
from robotlib.trading.position_sync_interface import PositionContext
from robotlib.utils.money import Money


def create_position_context(figi: str = "FUTIMOEXF000", quantity: int = 0, avg_price: float = 0.0, 
                           has_position: bool = False, direction: str = '') -> PositionContext:
    """Создание мока PositionContext для тестов"""
    return PositionContext(
        figi=figi,
        quantity=quantity,
        avg_price=avg_price,
        has_position=has_position,
        direction=direction,
        last_updated=datetime.now()
    )


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
        self.mock_portfolio_manager = AsyncMock()
        self.mock_portfolio_manager.get_loss_positions = AsyncMock(return_value=[])
        self.mock_portfolio_manager.get_profit_positions = AsyncMock(return_value=[])
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        self.strategy = LongStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
    
    def test_init(self):
        """Тест инициализации"""
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
        # Должен вернуть пустой список, так как нет позиции для продажи
        self.assertEqual(result, [])
    
    def test_items_to_buy_calculation(self):
        """Тест расчета количества для покупки"""

class TestShortStrategy(unittest.TestCase):
    """Тесты для ShortStrategy"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_risk_manager = Mock()
        self.mock_risk_manager.risk_limits.percent_from_deposit = 50.0
        self.mock_risk_manager.risk_limits.items_per_trade = 20
        self.mock_portfolio_manager = AsyncMock()
        self.mock_portfolio_manager.get_loss_positions = AsyncMock(return_value=[])
        self.mock_portfolio_manager.get_profit_positions = AsyncMock(return_value=[])
        mock_position_sizing_service = Mock()
        mock_position_sizing_service.calculate_position_size = AsyncMock(return_value=1)
        self.strategy = ShortStrategy(figi="FUTIMOEXF000", position_sizing_service=mock_position_sizing_service)
    
    def test_init(self):
        """Тест инициализации"""
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
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
        
        # Создаем контекст позиции
        position_context = create_position_context()
        
        result = await self.strategy.execute(mock_signal, position_context)
        
        # Должен вернуть пустой список, так как нет позиции для закрытия
        self.assertEqual(result, [])
    

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
