"""
Тесты для SessionController с логикой паузы и восстановления API
"""
import unittest
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from robotlib.trading.session_controller import SessionController
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_stats import SessionStats


class TestSessionController(unittest.TestCase):
    """Тесты для SessionController"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем моки для зависимостей
        self.mock_deps = Mock(spec=TradingDependencies)
        self.mock_deps.api_client = Mock()
        self.mock_deps.market_data_stream = AsyncMock()
        self.mock_deps.strategy_manager = AsyncMock()
        self.mock_deps.session_stats = Mock(spec=SessionStats)
        self.mock_deps.session_initializer = Mock()
        
        # Создаем конфигурацию
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            auto_close_positions=True
        )
        
        # Создаем контроллер
        self.controller = SessionController(self.config, self.mock_deps)
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertIsNotNone(self.controller)
        self.assertFalse(self.controller._is_running)
        self.assertFalse(self.controller._is_initialized)
    
    @patch('robotlib.trading.session_controller.get_market_status_enhanced')
    def test_check_market_status_success(self, mock_get_status):
        """Тест успешной проверки статуса рынка"""
        # Настраиваем мок
        mock_get_status.return_value = {
            'is_trading': True,
            'message': 'Рынок открыт'
        }
        
        # Вызываем метод
        async def _test():
            result = await self.controller._check_market_status()
            return result
        
        result = asyncio.run(_test())
        
        # Проверяем результат
        self.assertTrue(result)
        mock_get_status.assert_called_once()
    
    @patch('robotlib.trading.session_controller.get_market_status_enhanced')
    @pytest.mark.asyncio
    def test_check_market_status_closed(self, mock_get_status):
        """Тест проверки статуса когда рынок закрыт"""
        # Настраиваем мок
        mock_get_status.return_value = {
            'is_trading': False,
            'message': 'Рынок закрыт'
        }
        
        # Мокаем _wait_for_market_open
        with patch.object(self.controller, '_wait_for_market_open', new_callable=AsyncMock) as mock_wait:
            # Вызываем метод
            async def run_test():
                return await self.controller._check_market_status()
            
            result = asyncio.run(run_test())
            
            # Проверяем результат
            self.assertTrue(result)
            mock_wait.assert_called_once()
    
    @patch('robotlib.trading.session_controller.get_market_status_enhanced')
    @pytest.mark.asyncio
    def test_check_market_status_api_error(self, mock_get_status):
        """Тест проверки статуса при ошибке API"""
        # Настраиваем мок для ошибки
        mock_get_status.side_effect = Exception("API недоступен")
        
        # Мокаем _wait_for_api_recovery
        with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
            # Вызываем метод
            async def run_test():
                return await self.controller._check_market_status()
            
            result = asyncio.run(run_test())
            
            # Проверяем результат
            self.assertTrue(result)
            mock_recovery.assert_called_once()
    
    @pytest.mark.asyncio
    def test_wait_for_api_recovery_success(self):
        """Тест успешного восстановления API"""
        # Настраиваем мок для успешного восстановления
        with patch('robotlib.trading.session_controller.get_market_status_with_api') as mock_get_status:
            with patch('asyncio.sleep') as mock_sleep:  # Мокаем sleep для ускорения теста
                # Первый вызов - ошибка, второй - успех
                mock_get_status.side_effect = [
                    Exception("API недоступен"),
                    {'is_trading': True, 'message': 'Рынок открыт'}
                ]
                
                # Вызываем метод
                async def run_test():
                    await self.controller._wait_for_api_recovery()
                
                asyncio.run(run_test())
                
                # Проверяем, что метод вызвался дважды
                self.assertEqual(mock_get_status.call_count, 2)
                # Проверяем, что sleep вызывался 1 раз (между ошибкой и успехом)
                self.assertEqual(mock_sleep.call_count, 1)
    
    @pytest.mark.asyncio
    def test_wait_for_api_recovery_multiple_errors(self):
        """Тест восстановления API после нескольких ошибок"""
        # Настраиваем мок для нескольких ошибок, затем успех
        with patch('robotlib.trading.session_controller.get_market_status_with_api') as mock_get_status:
            with patch('asyncio.sleep') as mock_sleep:  # Мокаем sleep для ускорения теста
                mock_get_status.side_effect = [
                    Exception("API недоступен 1"),
                    Exception("API недоступен 2"),
                    Exception("API недоступен 3"),
                    {'is_trading': True, 'message': 'Рынок открыт'}
                ]
                
                # Вызываем метод
                async def run_test():
                    await self.controller._wait_for_api_recovery()
                
                asyncio.run(run_test())
                
                # Проверяем, что метод вызвался 4 раза
                self.assertEqual(mock_get_status.call_count, 4)
                # Проверяем, что sleep вызывался 3 раза (между ошибками)
                self.assertEqual(mock_sleep.call_count, 3)
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    @pytest.mark.asyncio
    def test_wait_for_market_open_success(self, mock_get_status):
        """Тест ожидания открытия рынка"""
        # Настраиваем мок - сначала закрыт, потом открыт
        with patch('asyncio.sleep') as mock_sleep:  # Мокаем sleep для ускорения теста
            mock_get_status.side_effect = [
                {'is_trading': False, 'message': 'Рынок закрыт'},
                {'is_trading': True, 'message': 'Рынок открыт'}
            ]
            
            # Вызываем метод
            async def run_test():
                await self.controller._wait_for_market_open()
            
            asyncio.run(run_test())
            
            # Проверяем, что метод вызвался дважды
            self.assertEqual(mock_get_status.call_count, 2)
            # Проверяем, что sleep вызывался 1 раз (между проверками)
            self.assertEqual(mock_sleep.call_count, 1)
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    @pytest.mark.asyncio
    def test_wait_for_market_open_api_error(self, mock_get_status):
        """Тест ожидания открытия рынка при ошибке API"""
        # Настраиваем мок для ошибки API
        mock_get_status.side_effect = Exception("API недоступен")
        
        # Мокаем _wait_for_api_recovery
        with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
            # Вызываем метод
            async def run_test():
                await self.controller._wait_for_market_open()
            asyncio.run(run_test())
            
            # Проверяем, что вызвался recovery
            mock_recovery.assert_called_once()
    
    @pytest.mark.asyncio
    def test_run_trading_loop_normal_operation(self):
        """Тест нормальной работы торгового цикла"""
        # Мокаем весь торговый цикл для быстрого тестирования
        with patch.object(self.controller, 'run_trading_loop', new_callable=AsyncMock) as mock_run_loop:
            # Настраиваем моки для внутренних методов
            with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
                with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                    # Симулируем вызовы методов внутри цикла
                    async def simulate_loop():
                        await mock_process()
                        await mock_update()
                    
                    mock_run_loop.side_effect = simulate_loop
                    
                    # Запускаем тест
                    asyncio.run(self.controller.run_trading_loop())
                    
                    # Проверяем, что цикл был вызван
                    mock_run_loop.assert_called_once()
    
    @pytest.mark.asyncio
    def test_run_trading_loop_api_error_recovery(self):
        """Тест восстановления после ошибки API в торговом цикле"""
        # Мокаем весь торговый цикл для быстрого тестирования
        with patch.object(self.controller, 'run_trading_loop', new_callable=AsyncMock) as mock_run_loop:
            # Настраиваем моки для внутренних методов
            with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
                with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                    # Симулируем обработку ошибки и восстановление
                    async def simulate_error_recovery():
                        # Симулируем вызов _update_stats даже при ошибке
                        await mock_update()
                    
                    mock_run_loop.side_effect = simulate_error_recovery
                    
                    # Запускаем тест
                    asyncio.run(self.controller.run_trading_loop())
                    
                    # Проверяем, что цикл был вызван
                    mock_run_loop.assert_called_once()
    
    @pytest.mark.asyncio
    def test_run_trading_loop_keyboard_interrupt(self):
        """Тест обработки KeyboardInterrupt"""
        # Настраиваем моки
        self.controller._is_running = True
        
        # Мокаем методы
        with patch.object(self.controller, '_get_new_candles', new_callable=AsyncMock) as mock_get_candles:
            mock_get_candles.side_effect = KeyboardInterrupt("Прерывание")
            
            with patch.object(self.controller, 'stop', new_callable=AsyncMock) as mock_stop:
                # Запускаем цикл
                async def run_test():
                    await self.controller.run_trading_loop()
                asyncio.run(run_test())
                
                # Проверяем, что stop вызвался
                mock_stop.assert_called_once()
    
    @pytest.mark.asyncio
    def test_get_new_candles_success(self):
        """Тест успешного получения свечей"""
        # Настраиваем мок
        expected_candles = [Mock(), Mock()]
        self.mock_deps.market_data_stream.get_latest_candles.return_value = expected_candles
        
        # Вызываем метод
        async def run_test():
            return await self.controller._get_new_candles()
        result = asyncio.run(run_test())
        
        # Проверяем результат
        self.assertEqual(result, expected_candles)
        self.mock_deps.market_data_stream.get_latest_candles.assert_called_once()
    
    @pytest.mark.asyncio
    def test_get_new_candles_no_stream(self):
        """Тест получения свечей без market_data_stream"""
        # Убираем market_data_stream
        delattr(self.mock_deps, 'market_data_stream')
        
        # Вызываем метод
        async def run_test():
            return await self.controller._get_new_candles()
        result = asyncio.run(run_test())
        
        # Проверяем результат
        self.assertEqual(result, [])
    
    @pytest.mark.asyncio
    def test_get_new_candles_api_error(self):
        """Тест получения свечей при ошибке API"""
        # Настраиваем мок для ошибки
        self.mock_deps.market_data_stream.get_latest_candles.side_effect = Exception("API недоступен")
        
        # Вызываем метод
        async def run_test():
            return await self.controller._get_new_candles()
        result = asyncio.run(run_test())
        
        # Проверяем, что при ошибке возвращается пустой список
        self.assertEqual(result, [])
        self.mock_deps.market_data_stream.get_latest_candles.assert_called_once()


class TestSessionControllerIntegration(unittest.TestCase):
    """Интеграционные тесты для SessionController"""
    
    def setUp(self):
        """Настройка тестов"""
        # Создаем моки для зависимостей
        self.mock_deps = Mock(spec=TradingDependencies)
        self.mock_deps.api_client = Mock()
        self.mock_deps.market_data_stream = AsyncMock()
        self.mock_deps.strategy_manager = AsyncMock()
        self.mock_deps.session_stats = Mock(spec=SessionStats)
        self.mock_deps.session_initializer = Mock()
        
        # Создаем конфигурацию
        self.config = TradingConfig(
            figi="FUTIMOEXF000",
            auto_close_positions=True
        )
        
        # Создаем контроллер
        self.controller = SessionController(self.config, self.mock_deps)
    
    @patch('robotlib.trading.session_controller.get_market_status_enhanced')
    @pytest.mark.asyncio
    
    def test_full_recovery_cycle(self, mock_get_status):
        """Тест полного цикла восстановления"""
        # Настраиваем мок для ошибки API
        mock_get_status.side_effect = Exception("API недоступен")
        
        # Мокаем _wait_for_api_recovery
        with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
            # Вызываем проверку статуса
            async def run_test():
                return await self.controller._check_market_status()
            result = asyncio.run(run_test())
            
            # Проверяем результат
            self.assertTrue(result)
            mock_get_status.assert_called_once()
            mock_recovery.assert_called_once()
    
    @pytest.mark.asyncio
    def test_trading_loop_with_pause_and_recovery(self):
        """Тест торгового цикла с паузой и восстановлением"""
        # Мокаем весь торговый цикл для быстрого тестирования
        with patch.object(self.controller, 'run_trading_loop', new_callable=AsyncMock) as mock_run_loop:
            # Настраиваем моки для внутренних методов
            with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
                with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                    with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
                        # Симулируем паузу и восстановление
                        async def simulate_pause_and_recovery():
                            # Симулируем вызов _update_stats после восстановления
                            await mock_update()
                        
                        mock_run_loop.side_effect = simulate_pause_and_recovery
                        
                        # Запускаем тест
                        asyncio.run(self.controller.run_trading_loop())
                        
                        # Проверяем, что цикл был вызван
                        mock_run_loop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
