"""
Тесты для API функций market hours
"""
import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from robotlib.utils.market_hours import get_market_status_with_api, is_trading_time_with_api


class TestMarketHoursAPI(unittest.TestCase):
    """Тесты для API функций market hours"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_api_client = Mock()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    async def test_get_market_status_with_api_success(self, mock_get_status_api):
        """Тест успешного получения статуса через API"""
        # Настраиваем мок
        expected_status = {
            'is_trading': True,
            'current_time': datetime.now(),
            'next_session': None,
            'time_until_next': None
        }
        mock_get_status_api.return_value = expected_status
        
        # Вызываем функцию
        result = await get_market_status_with_api()
        
        # Проверяем результат
        self.assertEqual(result, expected_status)
        mock_get_status_api.assert_called_once_with(None)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    async def test_get_market_status_with_api_with_datetime(self, mock_get_status_api):
        """Тест получения статуса с конкретным временем"""
        # Настраиваем мок
        test_time = datetime(2024, 1, 15, 12, 0)
        expected_status = {
            'is_trading': True,
            'current_time': test_time,
            'next_session': None,
            'time_until_next': None
        }
        mock_get_status_api.return_value = expected_status
        
        # Вызываем функцию
        result = await get_market_status_with_api(test_time)
        
        # Проверяем результат
        self.assertEqual(result, expected_status)
        mock_get_status_api.assert_called_once_with(test_time)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    async def test_get_market_status_with_api_error(self, mock_get_status_api):
        """Тест ошибки при получении статуса через API"""
        # Настраиваем мок для ошибки
        mock_get_status_api.side_effect = Exception("API недоступен")
        
        # Вызываем функцию и проверяем исключение
        with self.assertRaises(Exception) as context:
            await get_market_status_with_api()
        
        # Проверяем сообщение об ошибке
        self.assertIn("API недоступен", str(context.exception))
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    async def test_get_market_status_with_api_no_api(self):
        """Тест когда API недоступен"""
        # Вызываем функцию и проверяем исключение
        with self.assertRaises(Exception) as context:
            await get_market_status_with_api()
        
        # Проверяем сообщение об ошибке
        self.assertIn("Tinkoff API недоступен", str(context.exception))
        self.assertIn("Торговля невозможна без API", str(context.exception))
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    async def test_is_trading_time_with_api_success(self, mock_is_trading_time_api):
        """Тест успешной проверки торговых часов через API"""
        # Настраиваем мок
        mock_is_trading_time_api.return_value = True
        
        # Вызываем функцию
        result = await is_trading_time_with_api()
        
        # Проверяем результат
        self.assertTrue(result)
        mock_is_trading_time_api.assert_called_once_with(None)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    async def test_is_trading_time_with_api_with_datetime(self, mock_is_trading_time_api):
        """Тест проверки торговых часов с конкретным временем"""
        # Настраиваем мок
        test_time = datetime(2024, 1, 15, 12, 0)
        mock_is_trading_time_api.return_value = False
        
        # Вызываем функцию
        result = await is_trading_time_with_api(test_time)
        
        # Проверяем результат
        self.assertFalse(result)
        mock_is_trading_time_api.assert_called_once_with(test_time)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    async def test_is_trading_time_with_api_error(self, mock_is_trading_time_api):
        """Тест ошибки при проверке торговых часов через API"""
        # Настраиваем мок для ошибки
        mock_is_trading_time_api.side_effect = Exception("API недоступен")
        
        # Вызываем функцию и проверяем исключение
        with self.assertRaises(Exception) as context:
            await is_trading_time_with_api()
        
        # Проверяем сообщение об ошибке
        self.assertIn("API недоступен", str(context.exception))
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    async def test_is_trading_time_with_api_no_api(self):
        """Тест когда API недоступен для проверки торговых часов"""
        # Вызываем функцию и проверяем исключение
        with self.assertRaises(Exception) as context:
            await is_trading_time_with_api()
        
        # Проверяем сообщение об ошибке
        self.assertIn("Tinkoff API недоступен", str(context.exception))
        self.assertIn("Торговля невозможна без API", str(context.exception))


class TestMarketHoursAPIIntegration(unittest.TestCase):
    """Интеграционные тесты для API функций market hours"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_api_client = Mock()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    async def test_full_api_workflow(self, mock_is_trading_time, mock_get_status):
        """Тест полного рабочего процесса с API"""
        # Настраиваем моки
        mock_get_status.return_value = {
            'is_trading': True,
            'current_time': datetime.now(),
            'next_session': None,
            'time_until_next': None
        }
        mock_is_trading_time.return_value = True
        
        # Проверяем статус рынка
        status = await get_market_status_with_api()
        self.assertTrue(status['is_trading'])
        
        # Проверяем торговые часы
        is_trading = await is_trading_time_with_api()
        self.assertTrue(is_trading)
        
        # Проверяем, что API вызвался
        mock_get_status.assert_called_once()
        mock_is_trading_time.assert_called_once()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    async def test_api_error_handling(self, mock_is_trading_time, mock_get_status):
        """Тест обработки ошибок API"""
        # Настраиваем моки для ошибок
        mock_get_status.side_effect = Exception("Ошибка получения статуса")
        mock_is_trading_time.side_effect = Exception("Ошибка проверки времени")
        
        # Проверяем, что ошибки правильно обрабатываются
        with self.assertRaises(Exception) as context1:
            await get_market_status_with_api()
        self.assertIn("Ошибка получения статуса", str(context1.exception))
        
        with self.assertRaises(Exception) as context2:
            await is_trading_time_with_api()
        self.assertIn("Ошибка проверки времени", str(context2.exception))
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    async def test_no_api_available(self):
        """Тест когда API недоступен"""
        # Проверяем, что обе функции выдают правильные ошибки
        with self.assertRaises(Exception) as context1:
            await get_market_status_with_api()
        self.assertIn("Tinkoff API недоступен", str(context1.exception))
        
        with self.assertRaises(Exception) as context2:
            await is_trading_time_with_api()
        self.assertIn("Tinkoff API недоступен", str(context2.exception))


class TestMarketHoursAPIMocking(unittest.TestCase):
    """Тесты для мокирования API функций"""
    
    def setUp(self):
        """Настройка тестов"""
        self.mock_api_client = Mock()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    async def test_mock_api_success(self, mock_get_status_api):
        """Тест успешного мокирования API"""
        # Настраиваем мок для успешного ответа
        mock_response = {
            'is_trading': True,
            'current_time': datetime(2024, 1, 15, 12, 0),
            'next_session': {
                'start': datetime(2024, 1, 15, 19, 5),
                'end': datetime(2024, 1, 15, 23, 50),
                'name': 'Вечерняя сессия'
            },
            'time_until_next': 25200.0  # 7 часов
        }
        mock_get_status_api.return_value = mock_response
        
        # Вызываем функцию
        result = await get_market_status_with_api()
        
        # Проверяем результат
        self.assertEqual(result, mock_response)
        self.assertTrue(result['is_trading'])
        self.assertIsNotNone(result['next_session'])
        self.assertEqual(result['time_until_next'], 25200.0)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    async def test_mock_api_closed_market(self, mock_get_status_api):
        """Тест мокирования закрытого рынка"""
        # Настраиваем мок для закрытого рынка
        mock_response = {
            'is_trading': False,
            'current_time': datetime(2024, 1, 15, 2, 0),  # 2:00 ночи
            'next_session': {
                'start': datetime(2024, 1, 15, 9, 50),
                'end': datetime(2024, 1, 15, 10, 0),
                'name': 'Аукцион открытия'
            },
            'time_until_next': 28800.0  # 8 часов
        }
        mock_get_status_api.return_value = mock_response
        
        # Вызываем функцию
        result = await get_market_status_with_api()
        
        # Проверяем результат
        self.assertEqual(result, mock_response)
        self.assertFalse(result['is_trading'])
        self.assertIsNotNone(result['next_session'])
        self.assertEqual(result['time_until_next'], 28800.0)


if __name__ == '__main__':
    unittest.main()
