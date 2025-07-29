"""
Тесты для MarketDataStream
"""
import unittest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from collections import deque

from tinkoff.invest import Candle, MoneyValue, Quotation
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.signal_manager import SignalManager


class TestMarketDataStream(unittest.TestCase):
    """Тесты для MarketDataStream"""
    
    def setUp(self):
        """Настройка тестов"""
        self.api_client = Mock()
        self.signal_manager = Mock(spec=SignalManager)
        self.figi = "FUTIMOEXF000"
        
        self.market_data_stream = MarketDataStream(
            api_client=self.api_client,
            signal_manager=self.signal_manager,
            figi=self.figi,
            cache_size=10
        )
    
    def test_initialization(self):
        """Тест инициализации"""
        self.assertEqual(self.market_data_stream.figi, self.figi)
        self.assertEqual(self.market_data_stream.cached_candles.maxlen, 10)
        self.assertIsNone(self.market_data_stream.current_price)
        self.assertFalse(self.market_data_stream.is_running)
    
    def test_get_cache_size_empty(self):
        """Тест размера кэша когда он пуст"""
        self.assertEqual(self.market_data_stream.get_cache_size(), 0)
    
    def test_get_cached_candles_empty(self):
        """Тест получения кэшированных свечей когда кэш пуст"""
        candles = self.market_data_stream.get_cached_candles()
        self.assertEqual(len(candles), 0)
    
    def test_clear_cache(self):
        """Тест очистки кэша"""
        # Добавляем тестовые данные
        self.market_data_stream.cached_candles.append(Mock())
        self.market_data_stream.current_price = 100.0
        
        # Очищаем кэш
        self.market_data_stream.clear_cache()
        
        self.assertEqual(len(self.market_data_stream.cached_candles), 0)
        self.assertIsNone(self.market_data_stream.current_price)
    
    async def test_get_current_price_none(self):
        """Тест получения текущей цены когда её нет"""
        price = await self.market_data_stream.get_current_price()
        self.assertIsNone(price)
    
    async def test_get_current_price_with_value(self):
        """Тест получения текущей цены когда она есть"""
        self.market_data_stream.current_price = 1500.5
        price = await self.market_data_stream.get_current_price()
        self.assertEqual(price, 1500.5)
    
    async def test_get_latest_candles_empty_cache(self):
        """Тест получения последних свечей когда кэш пуст"""
        candles = await self.market_data_stream.get_latest_candles(5)
        self.assertEqual(len(candles), 0)
    
    async def test_get_latest_candles_with_data(self):
        """Тест получения последних свечей с данными"""
        # Создаем тестовые свечи
        test_candles = []
        for i in range(5):
            candle = Mock(spec=Candle)
            candle.figi = self.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            test_candles.append(candle)
            self.market_data_stream.cached_candles.append(candle)
        
        # Получаем последние 3 свечи
        latest_candles = await self.market_data_stream.get_latest_candles(3)
        
        self.assertEqual(len(latest_candles), 3)
        # Проверяем, что получили последние 3 свечи
        self.assertEqual(latest_candles[0].close.units, 1002)
        self.assertEqual(latest_candles[1].close.units, 1003)
        self.assertEqual(latest_candles[2].close.units, 1004)
    
    async def test_get_latest_candles_more_than_available(self):
        """Тест получения больше свечей чем есть в кэше"""
        # Добавляем 3 свечи
        for i in range(3):
            candle = Mock(spec=Candle)
            candle.figi = self.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            self.market_data_stream.cached_candles.append(candle)
        
        # Запрашиваем 10 свечей
        latest_candles = await self.market_data_stream.get_latest_candles(10)
        
        # Должны получить только 3 доступные свечи
        self.assertEqual(len(latest_candles), 3)
    
    def test_candle_caching(self):
        """Тест кэширования свечей"""
        # Создаем тестовую свечу
        candle = Mock(spec=Candle)
        candle.figi = self.figi
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1500, nano=500000000)  # 1500.5
        
        # Обрабатываем свечу
        self.market_data_stream._process_candle(candle)
        
        # Проверяем, что свеча добавилась в кэш
        self.assertEqual(len(self.market_data_stream.cached_candles), 1)
        self.assertEqual(self.market_data_stream.current_price, 1500.5)
    
    def test_candle_caching_wrong_figi(self):
        """Тест что свечи с неправильным FIGI не кэшируются"""
        # Создаем свечу с неправильным FIGI
        candle = Mock(spec=Candle)
        candle.figi = "WRONG_FIGI"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1500, nano=0)
        
        # Обрабатываем свечу
        self.market_data_stream._process_candle(candle)
        
        # Проверяем, что свеча НЕ добавилась в кэш
        self.assertEqual(len(self.market_data_stream.cached_candles), 0)
        self.assertIsNone(self.market_data_stream.current_price)
    
    def test_cache_size_limit(self):
        """Тест ограничения размера кэша"""
        # Добавляем больше свечей чем размер кэша
        for i in range(15):  # больше чем cache_size=10
            candle = Mock(spec=Candle)
            candle.figi = self.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            self.market_data_stream.cached_candles.append(candle)
        
        # Проверяем, что размер кэша не превышает лимит
        self.assertEqual(len(self.market_data_stream.cached_candles), 10)
        self.assertEqual(self.market_data_stream.get_cache_size(), 10)
    
    def test_add_candle_callback(self):
        """Тест добавления колбэка для свечей"""
        callback = Mock()
        self.market_data_stream.add_candle_callback(callback)
        
        self.assertIn(callback, self.market_data_stream.candle_callbacks)
    
    def test_remove_candle_callback(self):
        """Тест удаления колбэка для свечей"""
        callback = Mock()
        self.market_data_stream.add_candle_callback(callback)
        self.market_data_stream.remove_candle_callback(callback)
        
        self.assertNotIn(callback, self.market_data_stream.candle_callbacks)
    
    def test_add_signal_callback(self):
        """Тест добавления колбэка для сигналов"""
        callback = Mock()
        self.market_data_stream.add_signal_callback(callback)
        
        self.assertIn(callback, self.market_data_stream.signal_callbacks)
    
    def test_remove_signal_callback(self):
        """Тест удаления колбэка для сигналов"""
        callback = Mock()
        self.market_data_stream.add_signal_callback(callback)
        self.market_data_stream.remove_signal_callback(callback)
        
        self.assertNotIn(callback, self.market_data_stream.signal_callbacks)


if __name__ == '__main__':
    unittest.main()
