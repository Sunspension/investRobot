#!/usr/bin/env python3
"""
Тесты для TinkoffAPIClient
"""
import unittest
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from robotlib.trading.tinkoff_api_client import TinkoffAPIClient, OrderResult
from robotlib.utils.money import Money
from tinkoff.invest import OrderDirection, OrderType
from tinkoff.invest.schemas import MoneyValue, Quotation


class TestOrderResult(unittest.TestCase):
    """Тесты для класса OrderResult"""

    def test_order_result_creation(self):
        """Тест создания OrderResult"""
        result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=100.5,
            executed_quantity=10,
            commission=1.0
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.executed_price, 100.5)
        self.assertEqual(result.executed_quantity, 10)
        self.assertEqual(result.commission, 1.0)
        self.assertIsNone(result.error_message)

    def test_order_result_failure(self):
        """Тест OrderResult для неудачной операции"""
        result = OrderResult(
            success=False,
            error_message="Недостаточно средств"
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Недостаточно средств")
        self.assertIsNone(result.order_id)
        self.assertIsNone(result.executed_price)


class TestTinkoffAPIClient(unittest.TestCase):
    """Тесты для TinkoffAPIClient"""

    def setUp(self):
        """Настройка тестов"""
        self.token = "test_token"
        self.account_id = "test_account"
        self.sandbox_token = "test_sandbox_token"
        
        self.api_client = TinkoffAPIClient(
            token=self.token,
            account_id=self.account_id,
            sandbox_token=self.sandbox_token
        )

    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.api_client.token, self.token)
        self.assertEqual(self.api_client.account_id, self.account_id)
        self.assertEqual(self.api_client.sandbox_token, self.sandbox_token)
        self.assertIsNone(self.api_client.client)
        self.assertIsNone(self.api_client.services)

    def test_is_sandbox_property(self):
        """Тест свойства is_sandbox"""
        # С sandbox_token
        self.assertTrue(self.api_client.is_sandbox)
        
        # Без sandbox_token
        prod_client = TinkoffAPIClient(
            token=self.token,
            account_id=self.account_id
        )
        self.assertFalse(prod_client.is_sandbox)

    def test_float_to_money_value(self):
        """Тест конвертации float в MoneyValue"""
        money_value = self.api_client._float_to_money_value(100.5)
        
        self.assertEqual(money_value.currency, "rub")
        self.assertEqual(money_value.units, 100)
        self.assertEqual(money_value.nano, 500000000)

    def test_float_to_money_value_edge_cases(self):
        """Тест граничных случаев конвертации"""
        # Ноль
        zero = self.api_client._float_to_money_value(0.0)
        self.assertEqual(zero.units, 0)
        self.assertEqual(zero.nano, 0)
        
        # Отрицательное число
        negative = self.api_client._float_to_money_value(-100.5)
        self.assertEqual(negative.units, -100)
        self.assertEqual(negative.nano, -500000000)
        
        # Очень маленькое число
        small = self.api_client._float_to_money_value(0.000000001)
        self.assertEqual(small.units, 0)
        self.assertEqual(small.nano, 1)

    @patch('robotlib.trading.tinkoff_api_client.AsyncClient')
    @pytest.mark.asyncio

    async def test_context_manager_enter(self, mock_async_client):
        """Тест входа в контекстный менеджер"""
        mock_client_instance = Mock()
        mock_services = Mock()
        mock_async_client.return_value = mock_client_instance
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_services)
        mock_client_instance.__aexit__ = AsyncMock()  # Добавляем __aexit__
        
        async with self.api_client as client:
            self.assertEqual(client, self.api_client)
            self.assertEqual(self.api_client.client, mock_client_instance)
            self.assertEqual(self.api_client.services, mock_services)
            
            # Проверяем, что AsyncClient создан с правильными параметрами
            mock_async_client.assert_called_once_with(
                token=self.token,
                sandbox_token=self.sandbox_token
            )

    @patch('robotlib.trading.tinkoff_api_client.AsyncClient')
    @pytest.mark.asyncio

    async def test_context_manager_exit(self, mock_async_client):
        """Тест выхода из контекстного менеджера"""
        mock_client_instance = Mock()
        mock_services = Mock()
        mock_async_client.return_value = mock_client_instance
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_services)
        mock_client_instance.__aexit__ = AsyncMock()
        
        async with self.api_client:
            pass
        
        # Проверяем, что __aexit__ был вызван
        mock_client_instance.__aexit__.assert_called_once()

    @patch('robotlib.trading.tinkoff_api_client.check_market_open')
    @pytest.mark.asyncio

    async def test_check_market_availability_market_closed(self, mock_check_market):
        """Тест проверки доступности рынка - рынок закрыт"""
        mock_check_market.return_value = False
        
        # Мокаем services
        self.api_client.services = Mock()
        
        result = await self.api_client.check_market_availability()
        
        self.assertFalse(result)
        mock_check_market.assert_called_once()

    @patch('robotlib.trading.tinkoff_api_client.check_market_open')
    @pytest.mark.asyncio

    async def test_check_market_availability_market_open(self, mock_check_market):
        """Тест проверки доступности рынка - рынок открыт"""
        mock_check_market.return_value = True
        
        # Мокаем services и client
        mock_services = Mock()
        mock_users = Mock()
        mock_services.users = mock_users
        
        # Мокаем ответ get_accounts
        mock_accounts_response = Mock()
        mock_account = Mock()
        mock_account.id = self.account_id
        mock_accounts_response.accounts = [mock_account]
        mock_users.get_accounts = AsyncMock(return_value=mock_accounts_response)
        
        self.api_client.services = mock_services
        self.api_client.client = Mock()  # Устанавливаем client
        
        result = await self.api_client.check_market_availability()
        
        self.assertTrue(result)
        mock_check_market.assert_called_once()

    @patch('robotlib.trading.tinkoff_api_client.check_market_open')
    @pytest.mark.asyncio

    async def test_check_market_availability_no_client(self, mock_check_market):
        """Тест проверки доступности рынка - клиент не инициализирован"""
        mock_check_market.return_value = True
        
        # Не устанавливаем services
        result = await self.api_client.check_market_availability()
        
        self.assertFalse(result)

    @patch.object(TinkoffAPIClient, 'check_market_availability', new_callable=AsyncMock)
    @patch.object(TinkoffAPIClient, 'get_order_status', new_callable=AsyncMock)
    @pytest.mark.asyncio

    async def test_buy_market_success(self, mock_get_order_status, mock_check_market):
        """Тест успешной покупки по рынку"""
        mock_check_market.return_value = True
        
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.order_id = "12345"
        mock_response.executed_order_price = MoneyValue(currency="rub", units=100, nano=500000000)
        mock_response.total_order_amount = MoneyValue(currency="rub", units=1005, nano=0)
        mock_response.initial_order_price = MoneyValue(currency="rub", units=100, nano=500000000)
        mock_response.initial_commission = MoneyValue(currency="rub", units=0, nano=10000000)  # 0.01 руб
        
        mock_sandbox.post_sandbox_order = AsyncMock(return_value=mock_response)
        
        # Мокаем статус приказа для wait_for_order_execution
        mock_order_status = Mock()
        mock_order_status.execution_report_status = "EXECUTION_REPORT_STATUS_FILL"
        mock_order_status.executed_order_price = MoneyValue(currency="rub", units=100, nano=500000000)
        mock_order_status.lots_executed = 1
        mock_order_status.initial_commission = MoneyValue(currency="rub", units=0, nano=10000000)
        mock_get_order_status.return_value = mock_order_status
        
        self.api_client.services = mock_services
        
        result = await self.api_client.buy_market("FUTIMOEXF000", 1)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.executed_price, 100.5)  # 100 + 0.5
        self.assertEqual(result.executed_quantity, 1)
        self.assertEqual(result.commission, 0.01)  # Комиссия из мока
        self.assertIsNone(result.error_message)

    @patch.object(TinkoffAPIClient, 'check_market_availability', new_callable=AsyncMock)
    @pytest.mark.asyncio

    async def test_buy_market_api_error(self, mock_check_market):
        """Тест покупки с ошибкой API"""
        mock_check_market.return_value = True
        
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем исключение
        mock_sandbox.post_sandbox_order = AsyncMock(side_effect=Exception("API Error"))
        
        self.api_client.services = mock_services
        
        result = await self.api_client.buy_market("FUTIMOEXF000", 1)
        
        self.assertFalse(result.success)
        self.assertIn("API Error", result.error_message)
        self.assertIsNone(result.order_id)

    @patch.object(TinkoffAPIClient, 'check_market_availability', new_callable=AsyncMock)
    @patch.object(TinkoffAPIClient, 'get_order_status', new_callable=AsyncMock)
    @pytest.mark.asyncio

    async def test_sell_market_success(self, mock_get_order_status, mock_check_market):
        """Тест успешной продажи по рынку"""
        mock_check_market.return_value = True
        
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.order_id = "67890"
        mock_response.executed_order_price = MoneyValue(currency="rub", units=99, nano=500000000)
        mock_response.total_order_amount = MoneyValue(currency="rub", units=995, nano=0)
        mock_response.initial_order_price = MoneyValue(currency="rub", units=99, nano=500000000)
        mock_response.initial_commission = MoneyValue(currency="rub", units=0, nano=10000000)
        
        mock_sandbox.post_sandbox_order = AsyncMock(return_value=mock_response)
        
        # Мокаем статус приказа для wait_for_order_execution
        mock_order_status = Mock()
        mock_order_status.execution_report_status = "EXECUTION_REPORT_STATUS_FILL"
        mock_order_status.executed_order_price = MoneyValue(currency="rub", units=99, nano=500000000)
        mock_order_status.lots_executed = 1
        mock_order_status.initial_commission = MoneyValue(currency="rub", units=0, nano=10000000)
        mock_get_order_status.return_value = mock_order_status
        
        self.api_client.services = mock_services
        
        result = await self.api_client.sell_market("FUTIMOEXF000", 1)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "67890")
        self.assertEqual(result.executed_price, 99.5)  # 99 + 0.5
        self.assertEqual(result.executed_quantity, 1)
        self.assertEqual(result.commission, 0.01)  # Комиссия из мока

    @pytest.mark.asyncio


    async def test_get_portfolio_success(self):
        """Тест успешного получения портфеля"""
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.total_amount_portfolio = MoneyValue(currency="rub", units=1000000, nano=0)
        mock_response.positions = []
        
        mock_sandbox.get_sandbox_portfolio = AsyncMock(return_value=mock_response)
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_portfolio()
        
        self.assertEqual(result, mock_response)
        mock_sandbox.get_sandbox_portfolio.assert_called_once_with(account_id=self.account_id)

    @pytest.mark.asyncio


    async def test_get_portfolio_error(self):
        """Тест получения портфеля с ошибкой"""
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем исключение
        mock_sandbox.get_sandbox_portfolio = AsyncMock(side_effect=Exception("Portfolio Error"))
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_portfolio()
        
        self.assertIsNone(result)

    @pytest.mark.asyncio


    async def test_get_futures_margin_success(self):
        """Тест успешного получения маржи для фьючерса"""
        # Мокаем services
        mock_services = Mock()
        mock_instruments = Mock()
        mock_services.instruments = mock_instruments
        
        # Мокаем ответ от API
        mock_response = Mock()
        mock_response.initial_margin_on_buy = MoneyValue(currency="rub", units=1700, nano=0)
        mock_response.initial_margin_on_sell = MoneyValue(currency="rub", units=1700, nano=0)
        mock_response.min_price_increment = MoneyValue(currency="rub", units=0, nano=10000000)  # 0.01
        mock_response.min_price_increment_amount = MoneyValue(currency="rub", units=0, nano=100000000)  # 0.1
        
        mock_instruments.get_futures_margin = AsyncMock(return_value=mock_response)
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_futures_margin("FUTIMOEXF000")
        
        self.assertIsNotNone(result)
        self.assertEqual(result['initial_margin_on_buy'], 1700.0)
        self.assertEqual(result['initial_margin_on_sell'], 1700.0)
        self.assertEqual(result['min_price_increment'], 0.01)
        self.assertEqual(result['min_price_increment_amount'], 0.1)

    @pytest.mark.asyncio


    async def test_get_futures_margin_error(self):
        """Тест получения маржи с ошибкой"""
        # Мокаем services
        mock_services = Mock()
        mock_instruments = Mock()
        mock_services.instruments = mock_instruments
        
        # Мокаем исключение
        mock_instruments.get_futures_margin = AsyncMock(side_effect=Exception("Margin Error"))
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_futures_margin("FUTIMOEXF000")
        
        self.assertIsNone(result)

    @pytest.mark.asyncio


    async def test_get_operations_history_sandbox(self):
        """Тест получения истории операций в песочнице"""
        # Мокаем services
        mock_services = Mock()
        mock_sandbox = Mock()
        mock_services.sandbox = mock_sandbox
        
        # Мокаем ответ
        mock_response = Mock()
        mock_sandbox.get_sandbox_operations = AsyncMock(return_value=mock_response)
        
        self.api_client.services = mock_services
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        result = await self.api_client.get_operations_history(from_date, to_date)
        
        self.assertEqual(result, mock_response)
        mock_sandbox.get_sandbox_operations.assert_called_once_with(
            account_id=self.account_id,
            from_=from_date,
            to=to_date
        )

    @pytest.mark.asyncio


    async def test_get_operations_history_production(self):
        """Тест получения истории операций в продакшене"""
        # Создаем клиент без sandbox_token
        prod_client = TinkoffAPIClient(
            token=self.token,
            account_id=self.account_id
        )
        
        # Мокаем services
        mock_services = Mock()
        mock_operations = Mock()
        mock_services.operations = mock_operations
        
        # Мокаем ответ
        mock_response = Mock()
        mock_operations.get_operations = AsyncMock(return_value=mock_response)
        
        prod_client.services = mock_services
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        result = await prod_client.get_operations_history(from_date, to_date)
        
        self.assertEqual(result, mock_response)
        mock_operations.get_operations.assert_called_once_with(
            account_id=self.account_id,
            from_=from_date,
            to=to_date
        )

    @pytest.mark.asyncio


    async def test_get_candles_success(self):
        """Тест успешного получения свечей"""
        # Мокаем services
        mock_services = Mock()
        mock_market_data = Mock()
        mock_services.market_data = mock_market_data
        
        # Мокаем ответ
        mock_response = Mock()
        mock_response.candles = []  # Добавляем атрибут candles
        mock_market_data.get_candles = AsyncMock(return_value=mock_response)
        
        self.api_client.client = Mock()  # Добавляем client
        self.api_client.services = mock_services
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        result = await self.api_client.get_candles("FUTIMOEXF000", from_date, to_date, 1)
        
        self.assertEqual(result, mock_response)
        mock_market_data.get_candles.assert_called_once_with(
            figi="FUTIMOEXF000",
            from_=from_date,
            to=to_date,
            interval=1
        )

    @pytest.mark.asyncio


    async def test_get_candles_error(self):
        """Тест получения свечей с ошибкой"""
        # Мокаем services
        mock_services = Mock()
        mock_market_data = Mock()
        mock_services.market_data = mock_market_data
        
        # Мокаем исключение
        mock_market_data.get_candles = AsyncMock(side_effect=Exception("Candles Error"))
        
        self.api_client.services = mock_services
        
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()
        
        result = await self.api_client.get_candles("FUTIMOEXF000", from_date, to_date, 1)
        
        self.assertIsNone(result)

    @pytest.mark.asyncio


    async def test_create_market_data_stream(self):
        """Тест создания стрима рыночных данных"""
        # Мокаем services
        mock_services = Mock()
        mock_market_data_stream = Mock()
        mock_services.create_market_data_stream = Mock(return_value=mock_market_data_stream)
        
        self.api_client.services = mock_services
        
        result = await self.api_client.create_market_data_stream()
        
        self.assertEqual(result, mock_market_data_stream)
        mock_services.create_market_data_stream.assert_called_once()

    @pytest.mark.asyncio


    async def test_get_accounts_success(self):
        """Тест успешного получения аккаунтов"""
        # Мокаем services
        mock_services = Mock()
        mock_users = Mock()
        mock_services.users = mock_users
        
        # Мокаем ответ
        mock_response = Mock()
        mock_users.get_accounts = AsyncMock(return_value=mock_response)
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_accounts()
        
        self.assertEqual(result, mock_response)
        mock_users.get_accounts.assert_called_once()

    @pytest.mark.asyncio


    async def test_get_user_info_success(self):
        """Тест успешного получения информации о пользователе"""
        # Мокаем services
        mock_services = Mock()
        mock_users = Mock()
        mock_services.users = mock_users
        
        # Мокаем ответ
        mock_response = Mock()
        mock_users.get_info = AsyncMock(return_value=mock_response)
        
        self.api_client.services = mock_services
        
        result = await self.api_client.get_user_info()
        
        self.assertEqual(result, mock_response)
        mock_users.get_info.assert_called_once()


class TestTinkoffAPIClientIntegration(unittest.TestCase):
    """Интеграционные тесты для TinkoffAPIClient"""

    def setUp(self):
        """Настройка тестов"""
        self.token = "test_token"
        self.account_id = "test_account"
        self.sandbox_token = "test_sandbox_token"

    @patch('robotlib.trading.tinkoff_api_client.AsyncClient')
    @pytest.mark.asyncio

    async def test_full_context_manager_flow(self, mock_async_client):
        """Тест полного цикла контекстного менеджера"""
        # Настраиваем моки
        mock_client_instance = Mock()
        mock_services = Mock()
        mock_async_client.return_value = mock_client_instance
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_services)
        mock_client_instance.__aexit__ = AsyncMock()
        
        # Тестируем полный цикл
        async with TinkoffAPIClient(
            token=self.token,
            account_id=self.account_id,
            sandbox_token=self.sandbox_token
        ) as api_client:
            
            # Проверяем, что клиент инициализирован
            self.assertIsNotNone(api_client.client)
            self.assertIsNotNone(api_client.services)
            self.assertTrue(api_client.is_sandbox)
        
        # Проверяем, что __aexit__ был вызван
        mock_client_instance.__aexit__.assert_called_once()


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
for attr_name in dir(TestTinkoffAPIClient):
    attr = getattr(TestTinkoffAPIClient, attr_name)
    if attr_name.startswith('test_') and asyncio.iscoroutinefunction(attr):
        setattr(TestTinkoffAPIClient, attr_name, async_test(attr))

for attr_name in dir(TestTinkoffAPIClientIntegration):
    attr = getattr(TestTinkoffAPIClientIntegration, attr_name)
    if attr_name.startswith('test_') and asyncio.iscoroutinefunction(attr):
        setattr(TestTinkoffAPIClientIntegration, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()
