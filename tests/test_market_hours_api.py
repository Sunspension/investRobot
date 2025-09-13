#!/usr/bin/env python3
"""
Тесты для API функций market hours в формате pytest

ВАЖНО: Эти тесты НЕ делают реальные API вызовы к Tinkoff API.
Все внешние зависимости мокаются с помощью @patch декораторов.
Это обеспечивает быстрые, стабильные и изолированные тесты.

Для тестирования реальных API вызовов используйте интеграционные тесты отдельно.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from robotlib.utils.market_hours import get_market_status_with_api, is_trading_time_with_api


@pytest.fixture
def mock_api_client():
    """Фикстура для API клиента"""
    return Mock()


class TestMarketHoursAPIPytest:
    """Тесты для API функций market hours в формате pytest"""
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_get_market_status_with_api_success(self, mock_get_status_api):
        """Тест успешного получения статуса через API (с моком)"""
        # Настраиваем мок - НЕ делаем реальный API вызов
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
        assert result == expected_status
        mock_get_status_api.assert_called_once()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_get_market_status_with_api_with_datetime(self, mock_get_status_api):
        """Тест получения статуса с конкретным временем"""
        # Настраиваем мок
        test_time = datetime(2024, 1, 15, 10, 30, 0)
        expected_status = {
            'is_trading': False,
            'current_time': test_time,
            'next_session': 'evening',
            'time_until_next': 3600
        }
        mock_get_status_api.return_value = expected_status
        
        # Вызываем функцию с конкретным временем
        result = await get_market_status_with_api(test_time)
        
        # Проверяем результат
        assert result == expected_status
        mock_get_status_api.assert_called_once_with(test_time)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_get_market_status_with_api_error(self, mock_get_status_api):
        """Тест ошибки при получении статуса через API"""
        # Настраиваем мок для ошибки
        mock_get_status_api.side_effect = Exception("API Error")
        
        # Вызываем функцию и проверяем исключение
        with pytest.raises(Exception, match="API Error"):
            await get_market_status_with_api()
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    @pytest.mark.asyncio
    async def test_get_market_status_with_api_no_api(self):
        """Тест когда API недоступен"""
        # Вызываем функцию и проверяем исключение
        with pytest.raises(Exception, match="Tinkoff API недоступен"):
            await get_market_status_with_api()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    @pytest.mark.asyncio
    async def test_is_trading_time_with_api_success(self, mock_is_trading_time_api):
        """Тест успешной проверки торговых часов через API"""
        # Настраиваем мок
        mock_is_trading_time_api.return_value = True
        
        # Вызываем функцию
        result = await is_trading_time_with_api()
        
        # Проверяем результат
        assert result is True
        mock_is_trading_time_api.assert_called_once()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    @pytest.mark.asyncio
    async def test_is_trading_time_with_api_with_datetime(self, mock_is_trading_time_api):
        """Тест проверки торговых часов с конкретным временем"""
        # Настраиваем мок
        test_time = datetime(2024, 1, 15, 14, 30, 0)
        mock_is_trading_time_api.return_value = False
        
        # Вызываем функцию с конкретным временем
        result = await is_trading_time_with_api(test_time)
        
        # Проверяем результат
        assert result is False
        mock_is_trading_time_api.assert_called_once_with(test_time)
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    @pytest.mark.asyncio
    async def test_is_trading_time_with_api_error(self, mock_is_trading_time_api):
        """Тест ошибки при проверке торговых часов через API"""
        # Настраиваем мок для ошибки
        mock_is_trading_time_api.side_effect = Exception("API Error")
        
        # Вызываем функцию и проверяем исключение
        with pytest.raises(Exception, match="API Error"):
            await is_trading_time_with_api()
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    @pytest.mark.asyncio
    async def test_is_trading_time_with_api_no_api(self):
        """Тест когда API недоступен для проверки торговых часов"""
        # Вызываем функцию и проверяем исключение
        with pytest.raises(Exception, match="Tinkoff API недоступен"):
            await is_trading_time_with_api()


class TestMarketHoursAPIIntegrationPytest:
    """Интеграционные тесты для API функций market hours в формате pytest"""
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_full_api_workflow(self, mock_get_status, mock_is_trading_time):
        """Тест полного рабочего процесса с API"""
        # Настраиваем моки
        mock_get_status.return_value = {
            'is_trading': True,
            'current_time': datetime.now(),
            'next_session': None,
            'time_until_next': None
        }
        mock_is_trading_time.return_value = True
        
        # Вызываем функции
        status_result = await get_market_status_with_api()
        trading_result = await is_trading_time_with_api()
        
        # Проверяем результаты
        assert status_result['is_trading'] is True
        assert trading_result is True
        mock_get_status.assert_called_once()
        mock_is_trading_time.assert_called_once()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.is_trading_time_api')
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_get_status, mock_is_trading_time):
        """Тест обработки ошибок API"""
        # Настраиваем моки для ошибок
        mock_get_status.side_effect = Exception("Status API Error")
        mock_is_trading_time.side_effect = Exception("Trading API Error")
        
        # Проверяем, что обе функции выдают правильные ошибки
        with pytest.raises(Exception, match="Status API Error"):
            await get_market_status_with_api()
        
        with pytest.raises(Exception, match="Trading API Error"):
            await is_trading_time_with_api()
    
    @patch('robotlib.utils.market_hours.HAS_API', False)
    @pytest.mark.asyncio
    async def test_no_api_available(self):
        """Тест когда API недоступен"""
        # Проверяем, что обе функции выдают правильные ошибки
        with pytest.raises(Exception, match="Tinkoff API недоступен"):
            await get_market_status_with_api()
        
        with pytest.raises(Exception, match="Tinkoff API недоступен"):
            await is_trading_time_with_api()


class TestMarketHoursAPIMockingPytest:
    """Тесты мокирования API функций market hours в формате pytest"""
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_mock_api_success(self, mock_get_status_api):
        """Тест успешного мокирования API"""
        # Настраиваем мок для успешного ответа
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
        assert result == expected_status
        assert result['is_trading'] is True
        assert result['current_time'] is not None
        assert result['next_session'] is None
        assert result['time_until_next'] is None
        
        # Проверяем, что мок был вызван
        mock_get_status_api.assert_called_once()
    
    @patch('robotlib.utils.market_hours.HAS_API', True)
    @patch('robotlib.utils.market_hours.get_market_status_api')
    @pytest.mark.asyncio
    async def test_mock_api_closed_market(self, mock_get_status_api):
        """Тест мокирования закрытого рынка"""
        # Настраиваем мок для закрытого рынка
        expected_status = {
            'is_trading': False,
            'current_time': datetime.now(),
            'next_session': 'evening',
            'time_until_next': 3600
        }
        mock_get_status_api.return_value = expected_status
        
        # Вызываем функцию
        result = await get_market_status_with_api()
        
        # Проверяем результат
        assert result == expected_status
        assert result['is_trading'] is False
        assert result['next_session'] == 'evening'
        assert result['time_until_next'] == 3600
        
        # Проверяем, что мок был вызван
        mock_get_status_api.assert_called_once()
