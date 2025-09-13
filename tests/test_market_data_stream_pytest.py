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
def market_data_stream(api_client, signal_manager):
    """Фикстура для MarketDataStream"""
    return MarketDataStream(api_client, signal_manager, "FUTIMOEXF000")


class TestMarketDataStreamPytest:
    """Тесты для MarketDataStream в формате pytest"""
    
    def test_initialization(self, market_data_stream):
        """Тест инициализации"""
        assert market_data_stream.figi == "FUTIMOEXF000"
        assert market_data_stream.is_running is False
        assert len(market_data_stream.get_cached_candles()) == 0
        assert market_data_stream.current_price is None
    
    def test_candle_caching(self, market_data_stream):
        """Тест кэширования свечей"""
        # Создаем тестовую свечу
        candle = Mock(spec=Candle)
        candle.figi = "FUTIMOEXF000"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        
        # Добавляем свечу
        market_data_stream._process_candle(candle)
        
        # Проверяем, что свеча добавилась в кэш
        assert len(market_data_stream.get_cached_candles()) == 1
        assert market_data_stream.get_cached_candles()[0] == candle
    
    def test_candle_caching_wrong_figi(self, market_data_stream):
        """Тест кэширования свечи с неправильным FIGI"""
        # Создаем свечу с неправильным FIGI
        candle = Mock(spec=Candle)
        candle.figi = "WRONG_FIGI"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        
        # Добавляем свечу
        market_data_stream._process_candle(candle)
        
        # Проверяем, что свеча НЕ добавилась в кэш
        assert len(market_data_stream.get_cached_candles()) == 0
    
    def test_cache_size_limit(self, market_data_stream):
        """Тест ограничения размера кэша"""
        # Добавляем больше свечей чем размер кэша
        for i in range(150):  # cache_size по умолчанию 100
            candle = Mock(spec=Candle)
            candle.figi = "FUTIMOEXF000"
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            market_data_stream._process_candle(candle)
        
        # Проверяем, что размер кэша не превышает лимит
        assert len(market_data_stream.get_cached_candles()) == 100
    
    def test_clear_cache(self, market_data_stream):
        """Тест очистки кэша"""
        # Добавляем свечу
        candle = Mock(spec=Candle)
        candle.figi = "FUTIMOEXF000"
        candle.time = datetime.now()
        candle.close = MoneyValue(units=1000, nano=0)
        market_data_stream._process_candle(candle)
        
        # Очищаем кэш
        market_data_stream.clear_cache()
        
        assert len(market_data_stream.get_cached_candles()) == 0
        assert market_data_stream.current_price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_none(self, market_data_stream):
        """Тест получения текущей цены когда её нет"""
        price = await market_data_stream.get_current_price()
        assert price is None
    
    @pytest.mark.asyncio
    async def test_get_current_price_with_value(self, market_data_stream):
        """Тест получения текущей цены когда она есть"""
        market_data_stream._current_price = 1500.5
        price = await market_data_stream.get_current_price()
        assert price == 1500.5
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_empty_cache(self, market_data_stream):
        """Тест получения последних свечей когда кэш пуст"""
        candles = await market_data_stream.get_latest_candles(5)
        assert len(candles) == 0
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_with_data(self, market_data_stream):
        """Тест получения последних свечей с данными"""
        # Создаем тестовые свечи
        test_candles = []
        for i in range(5):
            candle = Mock(spec=Candle)
            candle.figi = market_data_stream.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            test_candles.append(candle)
        
        # Добавляем свечи в кэш
        for candle in test_candles:
            market_data_stream._process_candle(candle)
        
        # Получаем последние 3 свечи
        latest_candles = await market_data_stream.get_latest_candles(3)
        
        # Проверяем результат
        assert len(latest_candles) == 3
        assert latest_candles[0].close.units == 1002
        assert latest_candles[1].close.units == 1003
        assert latest_candles[2].close.units == 1004
    
    @pytest.mark.asyncio
    async def test_get_latest_candles_more_than_available(self, market_data_stream):
        """Тест получения больше свечей чем есть в кэше"""
        # Добавляем 3 свечи
        for i in range(3):
            candle = Mock(spec=Candle)
            candle.figi = market_data_stream.figi
            candle.time = datetime.now()
            candle.close = MoneyValue(units=1000 + i, nano=0)
            market_data_stream._process_candle(candle)
        
        # Запрашиваем 5 свечей, но есть только 3
        latest_candles = await market_data_stream.get_latest_candles(5)
        
        # Проверяем, что получили все доступные свечи
        assert len(latest_candles) == 3
        assert latest_candles[0].close.units == 1000
        assert latest_candles[1].close.units == 1001
        assert latest_candles[2].close.units == 1002
    
    def test_add_candle_callback(self, market_data_stream):
        """Тест добавления колбэка для свечей"""
        callback = Mock()
        market_data_stream.add_candle_callback(callback)
        assert callback in market_data_stream._candle_callbacks
    
    def test_remove_candle_callback(self, market_data_stream):
        """Тест удаления колбэка для свечей"""
        callback = Mock()
        market_data_stream.add_candle_callback(callback)
        market_data_stream.remove_candle_callback(callback)
        assert callback not in market_data_stream._candle_callbacks
    
    def test_add_signal_callback(self, market_data_stream):
        """Тест добавления колбэка для сигналов"""
        callback = Mock()
        market_data_stream.add_signal_callback(callback)
        assert callback in market_data_stream._signal_callbacks
    
    def test_remove_signal_callback(self, market_data_stream):
        """Тест удаления колбэка для сигналов"""
        callback = Mock()
        market_data_stream.add_signal_callback(callback)
        market_data_stream.remove_signal_callback(callback)
        assert callback not in market_data_stream._signal_callbacks
    
    def test_get_cache_size_empty(self, market_data_stream):
        """Тест получения размера пустого кэша"""
        assert market_data_stream.get_cache_size() == 0
    
    def test_get_cached_candles_empty(self, market_data_stream):
        """Тест получения пустого кэша свечей"""
        candles = market_data_stream.get_cached_candles()
        assert len(candles) == 0
