#!/usr/bin/env python3
"""
Исправленные тесты для MarketDataStream в формате pytest
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from collections import deque

from tinkoff.invest import Candle, MoneyValue, Quotation
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading.candle_cache import CandleCache
from robotlib.trading.stream_watchdog import StreamWatchdog
from robotlib.trading.historical_data_loader import HistoricalDataLoader
from robotlib.signal_manager import SignalManager


@pytest.fixture
def api_client():
    """Фикстура для API клиента"""
    return Mock()


@pytest.fixture
def signal_manager():
    """Фикстура для SignalManager"""
    return Mock(spec=SignalManager)


@pytest.fixture
def stream(api_client):
    """Фикстура для MarketDataStream"""
    # Создаем компоненты
    candle_cache = CandleCache(cache_size=100)
    historical_loader = HistoricalDataLoader(api_client, "FUTIMOEXF000")
    watchdog = None  # Отключаем watchdog для тестов
    
    return MarketDataStream(
        api_client=api_client, 
        figi="FUTIMOEXF000", 
        candle_cache=candle_cache,
        historical_loader=historical_loader,
        watchdog=watchdog
    )


class TestMarketDataStreamPytest:
    """Тесты для MarketDataStream в формате pytest"""
    
    def test_initialization(self, stream):
        """Тест инициализации"""
        assert stream.figi == "FUTIMOEXF000"
        assert stream.is_running is False
        assert len(stream.get_cached_candles()) == 0
        assert stream.current_price is None
    
    def test_candle_caching(self, stream):
        """Тест кэширования свечей"""
        # Создаем тестовую свечу
        candle = Mock(spec=Candle)
        candle.figi = "FUTIMOEXF000"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        
        # Добавляем свечу
        stream._process_candle(candle)
        
        # Проверяем, что свеча добавилась в кэш
        assert len(stream.get_cached_candles()) == 1
        assert stream.get_cached_candles()[0] == candle
    
    def test_candle_caching_wrong_figi(self, stream):
        """Тест кэширования свечи с неправильным FIGI"""
        # Создаем свечу с неправильным FIGI
        candle = Mock(spec=Candle)
        candle.figi = "WRONG_FIGI"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        
        # Добавляем свечу
        stream._process_candle(candle)
        
        # Проверяем, что свеча НЕ добавилась в кэш
        assert len(stream.get_cached_candles()) == 0
    
    def test_cache_size_limit(self, stream):
        """Тест ограничения размера кэша"""
        # Добавляем больше свечей чем размер кэша
        for i in range(150):  # cache_size по умолчанию 100
            candle = Mock(spec=Candle)
            candle.figi = "FUTIMOEXF000"
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            stream._process_candle(candle)
        
        # Проверяем, что размер кэша не превышает лимит
        assert len(stream.get_cached_candles()) == 100
    
    def test_clear_cache(self, stream):
        """Тест очистки кэша"""
        # Добавляем свечу
        candle = Mock(spec=Candle)
        candle.figi = "FUTIMOEXF000"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        stream._process_candle(candle)
        
        # Очищаем кэш
        stream.clear_cache()
        
        assert len(stream.get_cached_candles()) == 0
        assert stream.current_price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_none(self, stream):
        """Тест получения текущей цены когда её нет"""
        price = await stream.get_current_price()
        assert price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_with_value(self, stream):
        """Тест получения текущей цены когда она есть"""
        # Создаем mock свечу для установки цены
        mock_candle = Mock()
        mock_candle.close.units = 1500
        mock_candle.close.nano = 500000000  # 0.5
        stream._candle_cache.add_candle(mock_candle)
        price = await stream.get_current_price()
        assert price == 1500.5
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_empty_cache(self, stream):
        """Тест получения последних свечей когда кэш пуст"""
        candles = await stream.get_latest_candles(5)
        assert len(candles) == 0
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_with_data(self, stream):
        """Тест получения последних свечей с данными"""
        # Создаем тестовые свечи
        test_candles = []
        for i in range(5):
            candle = Mock(spec=Candle)
            candle.figi = stream.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            test_candles.append(candle)
        
        # Добавляем свечи в кэш
        for candle in test_candles:
            stream._process_candle(candle)
        
        # Получаем последние 3 свечи
        latest_candles = await stream.get_latest_candles(3)
        
        # Проверяем результат
        assert len(latest_candles) == 3
        assert latest_candles[0].close.units == 1002
        assert latest_candles[1].close.units == 1003
        assert latest_candles[2].close.units == 1004
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_more_than_available(self, stream):
        """Тест получения больше свечей чем есть в кэше"""
        # Добавляем 3 свечи
        for i in range(3):
            candle = Mock(spec=Candle)
            candle.figi = stream.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            stream._process_candle(candle)
        
        # Запрашиваем 5 свечей, но есть только 3
        latest_candles = await stream.get_latest_candles(5)
        
        # Проверяем, что получили все доступные свечи
        assert len(latest_candles) == 3
        assert latest_candles[0].close.units == 1000
        assert latest_candles[1].close.units == 1001
        assert latest_candles[2].close.units == 1002
    
    def test_add_candle_callback(self, stream):
        """Тест добавления колбэка для свечей"""
        callback = Mock()
        stream.add_candle_callback(callback)
        assert callback in stream._candle_callbacks
    
    def test_remove_candle_callback(self, stream):
        """Тест удаления колбэка для свечей"""
        callback = Mock()
        stream.add_candle_callback(callback)
        stream.remove_candle_callback(callback)
        assert callback not in stream._candle_callbacks
    
    def test_add_signal_callback(self, stream):
        """Тест добавления колбэка для сигналов"""
        callback = Mock()
        stream.add_signal_callback(callback)
        assert callback in stream._signal_callbacks
    
    def test_remove_signal_callback(self, stream):
        """Тест удаления колбэка для сигналов"""
        callback = Mock()
        stream.add_signal_callback(callback)
        stream.remove_signal_callback(callback)
        assert callback not in stream._signal_callbacks
    
    def test_get_cache_size_empty(self, stream):
        """Тест получения размера пустого кэша"""
        assert stream.get_cache_size() == 0
    
    def test_get_cached_candles_empty(self, stream):
        """Тест получения пустого кэша свечей"""
        candles = stream.get_cached_candles()
        assert len(candles) == 0
