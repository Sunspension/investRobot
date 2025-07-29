"""
Тесты для OrderExecutor
"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio

from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.tinkoff_api_client import OrderResult


class TestOrderResult(unittest.TestCase):
    """Тесты для класса OrderResult"""
    
    def test_order_result_creation(self):
        """Тест создания OrderResult"""
        result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=100.5,
            executed_quantity=1,
            commission=0.1,
            error_message=None
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.executed_price, 100.5)
        self.assertEqual(result.executed_quantity, 1)
        self.assertEqual(result.commission, 0.1)
        self.assertIsNone(result.error_message)
    
    def test_order_result_failure(self):
        """Тест OrderResult для неудачной операции"""
        result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="API Error"
        )
        
        self.assertFalse(result.success)
        self.assertIsNone(result.order_id)
        self.assertIsNone(result.executed_price)
        self.assertEqual(result.executed_quantity, 0)
        self.assertIsNone(result.commission)
        self.assertEqual(result.error_message, "API Error")


class TestOrderExecutor(unittest.TestCase):
    """Тесты для OrderExecutor"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_api_client = Mock()
        self.executor = OrderExecutor(self.mock_api_client)
    
    def test_init(self):
        """Тест инициализации"""
        self.assertEqual(self.executor.api_client, self.mock_api_client)
        self.assertIsNotNone(self.executor.logger)
    
    async def test_check_market_availability_success(self):
        """Тест успешной проверки доступности рынка"""
        self.mock_api_client.check_market_availability = AsyncMock(return_value=True)
        
        result = await self.executor.check_market_availability()
        
        self.assertTrue(result)
        self.mock_api_client.check_market_availability.assert_called_once()
    
    async def test_check_market_availability_failure(self):
        """Тест неудачной проверки доступности рынка"""
        self.mock_api_client.check_market_availability = AsyncMock(return_value=False)
        
        result = await self.executor.check_market_availability()
        
        self.assertFalse(result)
        self.mock_api_client.check_market_availability.assert_called_once()
    
    async def test_place_order_success(self):
        """Тест успешного размещения приказа"""
        mock_result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=100.5,
            executed_quantity=1,
            commission=0.1,
            error_message=None
        )
        
        self.mock_api_client.place_order = AsyncMock(return_value=mock_result)
        
        result = await self.executor.place_order(
            figi="FUTIMOEXF000",
            direction="BUY",
            quantity=1,
            price=100.5
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.mock_api_client.place_order.assert_called_once_with(
            "FUTIMOEXF000", "BUY", 1, 100.5, None
        )
    
    async def test_place_order_failure(self):
        """Тест неудачного размещения приказа"""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="API Error"
        )
        
        self.mock_api_client.place_order = AsyncMock(return_value=mock_result)
        
        result = await self.executor.place_order(
            figi="FUTIMOEXF000",
            direction="SELL",
            quantity=1
        )
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "API Error")
        self.mock_api_client.place_order.assert_called_once_with(
            "FUTIMOEXF000", "SELL", 1, None, None
        )
    
    async def test_get_order_status_success(self):
        """Тест успешного получения статуса приказа"""
        mock_status = {"order_id": "12345", "status": "EXECUTED"}
        self.mock_api_client.get_order_status = AsyncMock(return_value=mock_status)
        
        result = await self.executor.get_order_status("12345")
        
        self.assertEqual(result, mock_status)
        self.mock_api_client.get_order_status.assert_called_once_with("12345")
    
    async def test_get_order_status_failure(self):
        """Тест неудачного получения статуса приказа"""
        self.mock_api_client.get_order_status = AsyncMock(return_value=None)
        
        result = await self.executor.get_order_status("12345")
        
        self.assertIsNone(result)
        self.mock_api_client.get_order_status.assert_called_once_with("12345")
    
    async def test_cancel_order_success(self):
        """Тест успешной отмены приказа"""
        self.mock_api_client.cancel_order = AsyncMock(return_value=True)
        
        result = await self.executor.cancel_order("12345")
        
        self.assertTrue(result)
        self.mock_api_client.cancel_order.assert_called_once_with("12345")
    
    async def test_cancel_order_failure(self):
        """Тест неудачной отмены приказа"""
        self.mock_api_client.cancel_order = AsyncMock(return_value=False)
        
        result = await self.executor.cancel_order("12345")
        
        self.assertFalse(result)
        self.mock_api_client.cancel_order.assert_called_once_with("12345")
    
    async def test_buy_market_success(self):
        """Тест успешной покупки по рынку"""
        mock_result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=None,  # Для market orders цена None
            executed_quantity=1,
            commission=None,
            error_message=None
        )
        
        self.mock_api_client.buy_market = AsyncMock(return_value=mock_result)
        
        result = await self.executor.buy_market("FUTIMOEXF000", 1)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.mock_api_client.buy_market.assert_called_once_with("FUTIMOEXF000", 1, True)
    
    async def test_buy_market_failure(self):
        """Тест неудачной покупки по рынку"""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="Market closed"
        )
        
        self.mock_api_client.buy_market = AsyncMock(return_value=mock_result)
        
        result = await self.executor.buy_market("FUTIMOEXF000", 1)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Market closed")
        self.mock_api_client.buy_market.assert_called_once_with("FUTIMOEXF000", 1, True)
    
    async def test_sell_market_success(self):
        """Тест успешной продажи по рынку"""
        mock_result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=None,  # Для market orders цена None
            executed_quantity=1,
            commission=None,
            error_message=None
        )
        
        self.mock_api_client.sell_market = AsyncMock(return_value=mock_result)
        
        result = await self.executor.sell_market("FUTIMOEXF000", 1)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.mock_api_client.sell_market.assert_called_once_with("FUTIMOEXF000", 1, True)
    
    async def test_sell_market_failure(self):
        """Тест неудачной продажи по рынку"""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="Insufficient funds"
        )
        
        self.mock_api_client.sell_market = AsyncMock(return_value=mock_result)
        
        result = await self.executor.sell_market("FUTIMOEXF000", 1)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Insufficient funds")
        self.mock_api_client.sell_market.assert_called_once_with("FUTIMOEXF000", 1, True)
    
    async def test_buy_limit_success(self):
        """Тест успешной покупки по лимиту"""
        mock_result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=100.5,
            executed_quantity=1,
            commission=0.1,
            error_message=None
        )
        
        self.mock_api_client.buy_limit = AsyncMock(return_value=mock_result)
        
        result = await self.executor.buy_limit("FUTIMOEXF000", 1, 100.5)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.executed_price, 100.5)
        self.mock_api_client.buy_limit.assert_called_once_with("FUTIMOEXF000", 1, 100.5)
    
    async def test_buy_limit_failure(self):
        """Тест неудачной покупки по лимиту"""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="Price too high"
        )
        
        self.mock_api_client.buy_limit = AsyncMock(return_value=mock_result)
        
        result = await self.executor.buy_limit("FUTIMOEXF000", 1, 100.5)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Price too high")
        self.mock_api_client.buy_limit.assert_called_once_with("FUTIMOEXF000", 1, 100.5)
    
    async def test_sell_limit_success(self):
        """Тест успешной продажи по лимиту"""
        mock_result = OrderResult(
            success=True,
            order_id="12345",
            executed_price=100.5,
            executed_quantity=1,
            commission=0.1,
            error_message=None
        )
        
        self.mock_api_client.sell_limit = AsyncMock(return_value=mock_result)
        
        result = await self.executor.sell_limit("FUTIMOEXF000", 1, 100.5)
        
        self.assertTrue(result.success)
        self.assertEqual(result.order_id, "12345")
        self.assertEqual(result.executed_price, 100.5)
        self.mock_api_client.sell_limit.assert_called_once_with("FUTIMOEXF000", 1, 100.5)
    
    async def test_sell_limit_failure(self):
        """Тест неудачной продажи по лимиту"""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            executed_price=None,
            executed_quantity=0,
            commission=None,
            error_message="Price too low"
        )
        
        self.mock_api_client.sell_limit = AsyncMock(return_value=mock_result)
        
        result = await self.executor.sell_limit("FUTIMOEXF000", 1, 100.5)
        
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Price too low")
        self.mock_api_client.sell_limit.assert_called_once_with("FUTIMOEXF000", 1, 100.5)
    
    async def test_api_client_error_handling(self):
        """Тест обработки ошибок API клиента"""
        self.mock_api_client.buy_market = AsyncMock(side_effect=Exception("Connection error"))
        
        # OrderExecutor должен передать исключение дальше
        with self.assertRaises(Exception) as context:
            await self.executor.buy_market("FUTIMOEXF000", 1)
        
        self.assertEqual(str(context.exception), "Connection error")
        self.mock_api_client.buy_market.assert_called_once_with("FUTIMOEXF000", 1, True)


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
for attr_name in dir(TestOrderExecutor):
    attr = getattr(TestOrderExecutor, attr_name)
    if asyncio.iscoroutinefunction(attr):
        setattr(TestOrderExecutor, attr_name, async_test(attr))


if __name__ == '__main__':
    unittest.main()

