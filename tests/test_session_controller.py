"""
Тесты для SessionController с логикой паузы и восстановления API
"""
import unittest
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
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
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
        mock_get_status.assert_called_once_with(self.mock_deps.api_client)
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
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
            result = await self.controller._check_market_status()
            
            # Проверяем результат
            self.assertTrue(result)
            mock_wait.assert_called_once()
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    async def test_check_market_status_api_error(self, mock_get_status):
        """Тест проверки статуса при ошибке API"""
        # Настраиваем мок для ошибки
        mock_get_status.side_effect = Exception("API недоступен")
        
        # Мокаем _wait_for_api_recovery
        with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
            # Вызываем метод
            result = await self.controller._check_market_status()
            
            # Проверяем результат
            self.assertTrue(result)
            mock_recovery.assert_called_once()
    
    async def test_wait_for_api_recovery_success(self):
        """Тест успешного восстановления API"""
        # Настраиваем мок для успешного восстановления
        with patch('robotlib.trading.session_controller.get_market_status_with_api') as mock_get_status:
            # Первый вызов - ошибка, второй - успех
            mock_get_status.side_effect = [
                Exception("API недоступен"),
                {'is_trading': True, 'message': 'Рынок открыт'}
            ]
            
            # Вызываем метод
            await self.controller._wait_for_api_recovery()
            
            # Проверяем, что метод вызвался дважды
            self.assertEqual(mock_get_status.call_count, 2)
    
    async def test_wait_for_api_recovery_multiple_errors(self):
        """Тест восстановления API после нескольких ошибок"""
        # Настраиваем мок для нескольких ошибок, затем успех
        with patch('robotlib.trading.session_controller.get_market_status_with_api') as mock_get_status:
            mock_get_status.side_effect = [
                Exception("API недоступен 1"),
                Exception("API недоступен 2"),
                Exception("API недоступен 3"),
                {'is_trading': True, 'message': 'Рынок открыт'}
            ]
            
            # Вызываем метод
            await self.controller._wait_for_api_recovery()
            
            # Проверяем, что метод вызвался 4 раза
            self.assertEqual(mock_get_status.call_count, 4)
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    async def test_wait_for_market_open_success(self, mock_get_status):
        """Тест ожидания открытия рынка"""
        # Настраиваем мок - сначала закрыт, потом открыт
        mock_get_status.side_effect = [
            {'is_trading': False, 'message': 'Рынок закрыт'},
            {'is_trading': True, 'message': 'Рынок открыт'}
        ]
        
        # Вызываем метод
        await self.controller._wait_for_market_open()
        
        # Проверяем, что метод вызвался дважды
        self.assertEqual(mock_get_status.call_count, 2)
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    async def test_wait_for_market_open_api_error(self, mock_get_status):
        """Тест ожидания открытия рынка при ошибке API"""
        # Настраиваем мок для ошибки API
        mock_get_status.side_effect = Exception("API недоступен")
        
        # Мокаем _wait_for_api_recovery
        with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
            # Вызываем метод
            await self.controller._wait_for_market_open()
            
            # Проверяем, что вызвался recovery
            mock_recovery.assert_called_once()
    
    async def test_run_trading_loop_normal_operation(self):
        """Тест нормальной работы торгового цикла"""
        # Настраиваем моки
        self.controller._is_running = True
        self.mock_deps.market_data_stream.get_latest_candles.return_value = []
        
        # Мокаем методы
        with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
            with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                # Запускаем цикл на короткое время
                task = asyncio.create_task(self.controller.run_trading_loop())
                await asyncio.sleep(0.1)  # Короткая пауза
                self.controller._is_running = False
                await task
                
                # Проверяем, что методы вызвались
                mock_process.assert_called()
                mock_update.assert_called()
    
    async def test_run_trading_loop_api_error_recovery(self):
        """Тест восстановления после ошибки API в торговом цикле"""
        # Настраиваем моки
        self.controller._is_running = True
        
        # Настраиваем мок для ошибки, затем успеха
        self.mock_deps.market_data_stream.get_latest_candles.side_effect = [
            Exception("API недоступен"),
            []
        ]
        
        # Мокаем методы
        with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
            with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
                    # Запускаем цикл на короткое время
                    task = asyncio.create_task(self.controller.run_trading_loop())
                    await asyncio.sleep(0.1)  # Короткая пауза
                    self.controller._is_running = False
                    await task
                    
                    # Проверяем, что recovery вызвался
                    mock_recovery.assert_called_once()
    
    async def test_run_trading_loop_keyboard_interrupt(self):
        """Тест обработки KeyboardInterrupt"""
        # Настраиваем моки
        self.controller._is_running = True
        
        # Мокаем методы
        with patch.object(self.controller, '_get_new_candles', new_callable=AsyncMock) as mock_get_candles:
            mock_get_candles.side_effect = KeyboardInterrupt("Прерывание")
            
            with patch.object(self.controller, 'stop', new_callable=AsyncMock) as mock_stop:
                # Запускаем цикл
                await self.controller.run_trading_loop()
                
                # Проверяем, что stop вызвался
                mock_stop.assert_called_once()
    
    async def test_get_new_candles_success(self):
        """Тест успешного получения свечей"""
        # Настраиваем мок
        expected_candles = [Mock(), Mock()]
        self.mock_deps.market_data_stream.get_latest_candles.return_value = expected_candles
        
        # Вызываем метод
        result = await self.controller._get_new_candles()
        
        # Проверяем результат
        self.assertEqual(result, expected_candles)
        self.mock_deps.market_data_stream.get_latest_candles.assert_called_once()
    
    async def test_get_new_candles_no_stream(self):
        """Тест получения свечей без market_data_stream"""
        # Убираем market_data_stream
        delattr(self.mock_deps, 'market_data_stream')
        
        # Вызываем метод
        result = await self.controller._get_new_candles()
        
        # Проверяем результат
        self.assertEqual(result, [])
    
    async def test_get_new_candles_api_error(self):
        """Тест получения свечей при ошибке API"""
        # Настраиваем мок для ошибки
        self.mock_deps.market_data_stream.get_latest_candles.side_effect = Exception("API недоступен")
        
        # Вызываем метод
        with self.assertRaises(Exception):
            await self.controller._get_new_candles()


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
    
    @patch('robotlib.trading.session_controller.get_market_status_with_api')
    async def test_full_recovery_cycle(self, mock_get_status):
        """Тест полного цикла восстановления"""
        # Настраиваем мок для полного цикла
        mock_get_status.side_effect = [
            # Первая проверка - ошибка API
            Exception("API недоступен"),
            # Вторая проверка - ошибка API
            Exception("API недоступен"),
            # Третья проверка - успех
            {'is_trading': True, 'message': 'Рынок открыт'}
        ]
        
        # Вызываем проверку статуса
        result = await self.controller._check_market_status()
        
        # Проверяем результат
        self.assertTrue(result)
        self.assertEqual(mock_get_status.call_count, 3)
    
    async def test_trading_loop_with_pause_and_recovery(self):
        """Тест торгового цикла с паузой и восстановлением"""
        # Настраиваем моки
        self.controller._is_running = True
        
        # Настраиваем мок для цикла: ошибка -> пауза -> успех
        self.mock_deps.market_data_stream.get_latest_candles.side_effect = [
            Exception("API недоступен"),
            []  # Успешное получение свечей
        ]
        
        # Мокаем методы
        with patch.object(self.controller, '_process_candles', new_callable=AsyncMock) as mock_process:
            with patch.object(self.controller, '_update_stats', new_callable=AsyncMock) as mock_update:
                with patch.object(self.controller, '_wait_for_api_recovery', new_callable=AsyncMock) as mock_recovery:
                    # Запускаем цикл на короткое время
                    task = asyncio.create_task(self.controller.run_trading_loop())
                    await asyncio.sleep(0.1)  # Короткая пауза
                    self.controller._is_running = False
                    await task
                    
                    # Проверяем, что recovery вызвался
                    mock_recovery.assert_called_once()
                    
                    # Проверяем, что после восстановления торговля продолжилась
                    mock_process.assert_called()
                    mock_update.assert_called()


if __name__ == '__main__':
    unittest.main()
