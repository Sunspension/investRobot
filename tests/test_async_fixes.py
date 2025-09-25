#!/usr/bin/env python3
"""
Исправленные async тесты в формате pytest
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
    class _Dummy:
        services = None
    return _Dummy()


@pytest.fixture
def stream(api_client):
    figi = "FUTIMOEXF000"
    # Создаем компоненты
    candle_cache = CandleCache(cache_size=100)
    historical_loader = HistoricalDataLoader(api_client, figi)
    watchdog = None  # Отключаем watchdog для тестов
    
    return MarketDataStream(
        api_client=api_client, 
        figi=figi, 
        candle_cache=candle_cache,
        historical_loader=historical_loader,
        watchdog=watchdog
    )


@pytest.fixture
def market_data_stream(stream: MarketDataStream) -> MarketDataStream:
    return stream


@pytest.mark.asyncio
async def test_get_current_price_none(market_data_stream):
    """Тест получения текущей цены когда её нет"""
    price = await market_data_stream.get_current_price()
    assert price is None


@pytest.mark.asyncio
async def test_get_current_price_with_value(market_data_stream):
    """Тест получения текущей цены когда она есть"""
    # Создаем mock свечу для установки цены
    mock_candle = Mock()
    mock_candle.close.units = 1500
    mock_candle.close.nano = 500000000  # 0.5
    market_data_stream._candle_cache.add_candle(mock_candle)
    price = await market_data_stream.get_current_price()
    assert price == 1500.5


@pytest.mark.asyncio
async def test_get_latest_candles_empty_cache(market_data_stream):
    """Тест получения последних свечей когда кэш пуст"""
    candles = await market_data_stream.get_latest_candles(5)
    assert len(candles) == 0


@pytest.mark.asyncio
async def test_get_latest_candles_with_data(market_data_stream):
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
async def test_get_latest_candles_more_than_available(market_data_stream):
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
