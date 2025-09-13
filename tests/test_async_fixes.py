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
from robotlib.signal_manager import SignalManager


@pytest.fixture
def market_data_stream():
    """Фикстура для MarketDataStream"""
    api_client = Mock()
    signal_manager = Mock(spec=SignalManager)
    figi = "FUTIMOEXF000"
    return MarketDataStream(api_client, signal_manager, figi)


@pytest.mark.asyncio
async def test_get_current_price_none(market_data_stream):
    """Тест получения текущей цены когда её нет"""
    price = await market_data_stream.get_current_price()
    assert price is None


@pytest.mark.asyncio
async def test_get_current_price_with_value(market_data_stream):
    """Тест получения текущей цены когда она есть"""
    market_data_stream._current_price = 1500.5
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
