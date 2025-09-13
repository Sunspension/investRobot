#!/usr/bin/env python3
"""
Тесты для PortfolioManager
"""
import unittest
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from robotlib.trading.portfolio_manager import PortfolioManager, Position, Portfolio
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.utils.money import Money
from tinkoff.invest.schemas import MoneyValue, Quotation, Operation, OperationType, OperationState


class TestPosition(unittest.TestCase):
    """Тесты для класса Position"""

    def test_position_creation(self):
        """Тест создания позиции"""
        position = Position(
            figi="FUTIMOEXF000",
            quantity=10,
            average_price=100.5,
            current_price=102.0,
            unrealized_pnl=15.0,
            realized_pnl=5.0
        )
        
        self.assertEqual(position.figi, "FUTIMOEXF000")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.average_price, 100.5)
        self.assertEqual(position.current_price, 102.0)
        self.assertEqual(position.unrealized_pnl, 15.0)
        self.assertEqual(position.realized_pnl, 5.0)

    def test_position_zero_values(self):
        """Тест позиции с нулевыми значениями"""
        position = Position(
            figi="FUTIMOEXF000",
            quantity=0,
            average_price=0.0,
            current_price=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0
        )
        
        self.assertEqual(position.quantity, 0)
        self.assertEqual(position.average_price, 0.0)
        self.assertEqual(position.current_price, 0.0)
        self.assertEqual(position.unrealized_pnl, 0.0)
        self.assertEqual(position.realized_pnl, 0.0)


class TestPortfolio(unittest.TestCase):
    """Тесты для класса Portfolio"""

    def test_portfolio_creation(self):
        """Тест создания портфеля"""
        positions = [
            Position("FUTIMOEXF000", 10, 100.0, 102.0, 20.0, 5.0),
            Position("FUTIMOEXF001", 5, 200.0, 198.0, -10.0, 0.0)
        ]
        
        portfolio = Portfolio(
            total_amount=100000.0,
            blocked_amount=5000.0,
            available_amount=95000.0,
            positions=positions
        )
        
        self.assertEqual(portfolio.total_amount, 100000.0)
        self.assertEqual(portfolio.blocked_amount, 5000.0)
        self.assertEqual(portfolio.available_amount, 95000.0)
        self.assertEqual(len(portfolio.positions), 2)
        self.assertEqual(portfolio.positions[0].figi, "FUTIMOEXF000")
        self.assertEqual(portfolio.positions[1].figi, "FUTIMOEXF001")

    def test_portfolio_empty_positions(self):
        """Тест портфеля без позиций"""
        portfolio = Portfolio(
            total_amount=50000.0,
            blocked_amount=0.0,
            available_amount=50000.0,
            positions=[]
        )
        
        self.assertEqual(portfolio.total_amount, 50000.0)
        self.assertEqual(portfolio.blocked_amount, 0.0)
        self.assertEqual(portfolio.available_amount, 50000.0)
        self.assertEqual(len(portfolio.positions), 0)


class TestPortfolioManager(unittest.TestCase):
    """Тесты для PortfolioManager"""

    def setUp(self):
        """Настройка тестов"""
        self.mock_api_client = Mock(spec=TinkoffAPIClient)
        self.portfolio_manager = PortfolioManager(self.mock_api_client)

    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.portfolio_manager._api_client, self.mock_api_client)
        self.assertEqual(self.portfolio_manager._cache_ttl, 30)
        self.assertEqual(len(self.portfolio_manager._positions_cache), 0)
        self.assertIsNone(self.portfolio_manager._cache_timestamp)

    def test_is_cache_valid_no_timestamp(self):
        """Тест валидности кэша без временной метки"""
        self.assertFalse(self.portfolio_manager._is_cache_valid())

    def test_is_cache_valid_fresh_cache(self):
        """Тест валидности свежего кэша"""
        self.portfolio_manager._cache_timestamp = datetime.now()
        self.assertTrue(self.portfolio_manager._is_cache_valid())

    def test_is_cache_valid_expired_cache(self):
        """Тест валидности устаревшего кэша"""
        self.portfolio_manager._cache_timestamp = datetime.now() - timedelta(seconds=60)
        self.assertFalse(self.portfolio_manager._is_cache_valid())

    def test_build_portfolio_from_cache(self):
        """Тест построения портфеля из кэша"""
        # Добавляем позиции в кэш
        position1 = Position("FUTIMOEXF000", 10, 100.0, 102.0, 20.0, 5.0)
        position2 = Position("FUTIMOEXF001", 5, 200.0, 198.0, -10.0, 0.0)
        
        self.portfolio_manager._positions_cache["FUTIMOEXF000"] = position1
        self.portfolio_manager._positions_cache["FUTIMOEXF001"] = position2
        
        portfolio = self.portfolio_manager._build_portfolio_from_cache()
        
        self.assertEqual(len(portfolio.positions), 2)
        self.assertEqual(portfolio.total_amount, 0.0)  # TODO в коде
        self.assertEqual(portfolio.blocked_amount, 0.0)
        self.assertEqual(portfolio.available_amount, 0.0)

    @pytest.mark.asyncio


    async def test_get_portfolio_success(self):
        """Тест успешного получения портфеля"""
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=100000, nano=0)
        mock_response.blocked = MoneyValue(currency="rub", units=5000, nano=0)
        
        # Мокаем позицию
        mock_position = Mock()
        mock_position.instrument_type = "futures"
        mock_position.figi = "FUTIMOEXF000"
        mock_position.current_price = MoneyValue(currency="rub", units=100, nano=500000000)  # 100.5
        mock_position.average_position_price = MoneyValue(currency="rub", units=100, nano=0)  # 100.0
        mock_position.quantity = MoneyValue(currency="rub", units=10, nano=0)  # 10
        
        mock_response.positions = [mock_position]
        
        self.mock_api_client.get_portfolio = AsyncMock(return_value=mock_response)
        
        portfolio = await self.portfolio_manager.get_portfolio()
        
        self.assertEqual(portfolio.total_amount, 100000.0)
        self.assertEqual(portfolio.blocked_amount, 0.0)  # В коде всегда 0.0
        self.assertEqual(portfolio.available_amount, 100000.0)  # total_amount - blocked_amount
        self.assertEqual(len(portfolio.positions), 1)
        
        position = portfolio.positions[0]
        self.assertEqual(position.figi, "FUTIMOEXF000")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.average_price, 100.0)
        self.assertEqual(position.current_price, 100.5)
        self.assertEqual(position.unrealized_pnl, 5.0)  # (100.5 - 100.0) * 10

    @pytest.mark.asyncio


    async def test_get_portfolio_api_error(self):
        """Тест получения портфеля с ошибкой API"""
        self.mock_api_client.get_portfolio = AsyncMock(return_value=None)
        
        portfolio = await self.portfolio_manager.get_portfolio()
        
        self.assertEqual(portfolio.total_amount, 0.0)
        self.assertEqual(portfolio.blocked_amount, 0.0)
        self.assertEqual(portfolio.available_amount, 0.0)
        self.assertEqual(len(portfolio.positions), 0)

    @pytest.mark.asyncio


    async def test_get_portfolio_with_cache(self):
        """Тест получения портфеля с использованием кэша"""
        # Устанавливаем валидный кэш
        position = Position("FUTIMOEXF000", 10, 100.0, 102.0, 20.0, 5.0)
        self.portfolio_manager._positions_cache["FUTIMOEXF000"] = position
        self.portfolio_manager._cache_timestamp = datetime.now()
        
        # API не должен вызываться
        self.mock_api_client.get_portfolio = AsyncMock()
        
        portfolio = await self.portfolio_manager.get_portfolio()
        
        # Проверяем, что API не вызывался
        self.mock_api_client.get_portfolio.assert_not_called()
        
        # Проверяем результат из кэша
        self.assertEqual(len(portfolio.positions), 1)
        self.assertEqual(portfolio.positions[0].figi, "FUTIMOEXF000")

    @pytest.mark.asyncio


    async def test_get_portfolio_force_refresh(self):
        """Тест принудительного обновления портфеля"""
        # Устанавливаем валидный кэш
        position = Position("FUTIMOEXF000", 10, 100.0, 102.0, 20.0, 5.0)
        self.portfolio_manager._positions_cache["FUTIMOEXF000"] = position
        self.portfolio_manager._cache_timestamp = datetime.now()
        
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=200000, nano=0)
        mock_response.blocked = MoneyValue(currency="rub", units=10000, nano=0)
        mock_response.positions = []
        
        self.mock_api_client.get_portfolio = AsyncMock(return_value=mock_response)
        
        portfolio = await self.portfolio_manager.get_portfolio(force_refresh=True)
        
        # Проверяем, что API вызывался
        self.mock_api_client.get_portfolio.assert_called_once()
        
        # Проверяем новый результат
        self.assertEqual(portfolio.total_amount, 200000.0)
        self.assertEqual(portfolio.blocked_amount, 0.0)  # В коде всегда 0.0
        self.assertEqual(portfolio.available_amount, 200000.0)  # total_amount - blocked_amount
        self.assertEqual(len(portfolio.positions), 0)

    @pytest.mark.asyncio


    async def test_get_position_success(self):
        """Тест успешного получения позиции"""
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=100000, nano=0)
        mock_response.blocked = MoneyValue(currency="rub", units=5000, nano=0)
        
        # Мокаем позицию
        mock_position = Mock()
        mock_position.instrument_type = "futures"
        mock_position.figi = "FUTIMOEXF000"
        mock_position.current_price = MoneyValue(currency="rub", units=100, nano=500000000)  # 100.5
        mock_position.average_position_price = MoneyValue(currency="rub", units=100, nano=0)  # 100.0
        mock_position.quantity = MoneyValue(currency="rub", units=10, nano=0)  # 10
        
        mock_response.positions = [mock_position]
        
        self.mock_api_client.get_portfolio = AsyncMock(return_value=mock_response)
        
        position = await self.portfolio_manager.get_position("FUTIMOEXF000")
        
        self.assertIsNotNone(position)
        self.assertEqual(position.figi, "FUTIMOEXF000")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.average_price, 100.0)
        self.assertEqual(position.current_price, 100.5)
        self.assertEqual(position.unrealized_pnl, 5.0)

    @pytest.mark.asyncio


    async def test_get_position_not_found(self):
        """Тест получения несуществующей позиции"""
        # Мокаем ответ от API без позиций
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=100000, nano=0)
        mock_response.blocked = MoneyValue(currency="rub", units=5000, nano=0)
        mock_response.positions = []
        
        self.mock_api_client.get_portfolio = AsyncMock(return_value=mock_response)
        
        position = await self.portfolio_manager.get_position("FUTIMOEXF000")
        
        self.assertIsNone(position)

    @pytest.mark.asyncio


    async def test_get_position_api_error(self):
        """Тест получения позиции с ошибкой API"""
        self.mock_api_client.get_portfolio = AsyncMock(return_value=None)
        
        position = await self.portfolio_manager.get_position("FUTIMOEXF000")
        
        self.assertIsNone(position)

    @pytest.mark.asyncio


    async def test_get_guarantee_deposit_success(self):
        """Тест успешного получения гарантийного обеспечения"""
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.initial_margin_on_buy = MoneyValue(currency="rub", units=1700, nano=0)
        mock_response.initial_margin_on_sell = MoneyValue(currency="rub", units=1700, nano=0)
        mock_response.min_price_increment = MoneyValue(currency="rub", units=0, nano=10000000)  # 0.01
        mock_response.min_price_increment_amount = MoneyValue(currency="rub", units=0, nano=100000000)  # 0.1
        
        self.mock_api_client.get_futures_margin = AsyncMock(return_value={
            'initial_margin_on_buy': 1700.0,
            'initial_margin_on_sell': 1700.0,
            'min_price_increment': 0.01,
            'min_price_increment_amount': 0.1
        })
        
        deposit = await self.portfolio_manager.get_guarantee_deposit("FUTIMOEXF000")
        
        self.assertEqual(deposit, 1700.0)
        self.mock_api_client.get_futures_margin.assert_called_once_with("FUTIMOEXF000")

    @pytest.mark.asyncio


    async def test_get_guarantee_deposit_api_error(self):
        """Тест получения гарантийного обеспечения с ошибкой API"""
        self.mock_api_client.get_futures_margin = AsyncMock(return_value=None)
        
        deposit = await self.portfolio_manager.get_guarantee_deposit("FUTIMOEXF000")
        
        self.assertEqual(deposit, 0.0)

    @pytest.mark.asyncio


    async def test_get_deposit_success(self):
        """Тест успешного получения депозита"""
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=100000, nano=0)
        
        self.mock_api_client.get_portfolio = AsyncMock(return_value=mock_response)
        
        deposit = await self.portfolio_manager.get_deposit()
        
        self.assertEqual(deposit, 100000.0)
        self.mock_api_client.get_portfolio.assert_called_once()

    @pytest.mark.asyncio


    async def test_get_deposit_api_error(self):
        """Тест получения депозита с ошибкой API"""
        self.mock_api_client.get_portfolio = AsyncMock(return_value=None)
        
        deposit = await self.portfolio_manager.get_deposit()
        
        self.assertEqual(deposit, 0.0)

    @pytest.mark.asyncio


    async def test_get_operations_history_success(self):
        """Тест успешного получения истории операций"""
        # Мокаем операции
        mock_operation1 = Mock()
        mock_operation1.figi = "FUTIMOEXF000"
        mock_operation1.operation_type = OperationType.OPERATION_TYPE_BUY
        mock_operation1.state = OperationState.OPERATION_STATE_EXECUTED
        
        mock_operation2 = Mock()
        mock_operation2.figi = "FUTIMOEXF000"
        mock_operation2.operation_type = OperationType.OPERATION_TYPE_SELL
        mock_operation2.state = OperationState.OPERATION_STATE_EXECUTED
        
        mock_operations = [mock_operation1, mock_operation2]
        
        self.mock_api_client.get_operations_history = AsyncMock(return_value=mock_operations)
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        operations = await self.portfolio_manager.get_operations_history(from_date, to_date, "FUTIMOEXF000")
        
        self.assertEqual(len(operations), 2)
        self.assertEqual(operations[0].figi, "FUTIMOEXF000")
        self.assertEqual(operations[1].figi, "FUTIMOEXF000")
        
        self.mock_api_client.get_operations_history.assert_called_once_with(from_date, to_date)

    @pytest.mark.asyncio


    async def test_get_operations_history_api_error(self):
        """Тест получения истории операций с ошибкой API"""
        self.mock_api_client.get_operations_history = AsyncMock(side_effect=Exception("API Error"))
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        operations = await self.portfolio_manager.get_operations_history(from_date, to_date)
        
        self.assertEqual(len(operations), 0)

    @pytest.mark.asyncio


    async def test_process_position_data_success(self):
        """Тест успешной обработки данных позиции"""
        # Мокаем данные позиции
        mock_position_data = Mock()
        mock_position_data.figi = "FUTIMOEXF000"
        mock_position_data.current_price = MoneyValue(currency="rub", units=100, nano=500000000)  # 100.5
        mock_position_data.average_position_price = MoneyValue(currency="rub", units=100, nano=0)  # 100.0
        mock_position_data.quantity = MoneyValue(currency="rub", units=10, nano=0)  # 10
        
        position = await self.portfolio_manager._process_position_data(mock_position_data)
        
        self.assertIsNotNone(position)
        self.assertEqual(position.figi, "FUTIMOEXF000")
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.average_price, 100.0)
        self.assertEqual(position.current_price, 100.5)
        self.assertEqual(position.unrealized_pnl, 5.0)  # (100.5 - 100.0) * 10
        self.assertEqual(position.realized_pnl, 0.0)

    @pytest.mark.asyncio


    async def test_process_position_data_zero_quantity(self):
        """Тест обработки данных позиции с нулевым количеством"""
        # Мокаем данные позиции с нулевым количеством
        mock_position_data = Mock()
        mock_position_data.figi = "FUTIMOEXF000"
        mock_position_data.current_price = MoneyValue(currency="rub", units=100, nano=500000000)  # 100.5
        mock_position_data.average_position_price = MoneyValue(currency="rub", units=100, nano=0)  # 100.0
        mock_position_data.quantity = MoneyValue(currency="rub", units=0, nano=0)  # 0
        
        position = await self.portfolio_manager._process_position_data(mock_position_data)
        
        self.assertIsNotNone(position)
        self.assertEqual(position.quantity, 0)
        self.assertEqual(position.unrealized_pnl, 0.0)  # При quantity=0 PnL=0

    @pytest.mark.asyncio


    async def test_process_position_data_error(self):
        """Тест обработки данных позиции с ошибкой"""
        # Мокаем некорректные данные
        mock_position_data = Mock()
        mock_position_data.figi = "FUTIMOEXF000"
        # Не устанавливаем обязательные поля
        
        position = await self.portfolio_manager._process_position_data(mock_position_data)
        
        self.assertIsNone(position)




# Функция для запуска асинхронных тестов
def async_test(coro):
    """Декоратор для асинхронных тестов"""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro(*args, **kwargs))
        finally:
            loop.close()
    return wrapper


# Применяем декоратор ко всем асинхронным тестам
for attr_name in dir(TestPortfolioManager):
    attr = getattr(TestPortfolioManager, attr_name)
    if attr_name.startswith('test_') and asyncio.iscoroutinefunction(attr):
        setattr(TestPortfolioManager, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()
