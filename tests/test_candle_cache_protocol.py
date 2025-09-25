#!/usr/bin/env python3
"""
Тесты для демонстрации гибкости протокола CandleCacheable
"""
import pytest
from unittest.mock import Mock
from tinkoff.invest import Candle, MoneyValue

from robotlib.trading.candle_cache import CandleCache
from robotlib.trading.candle_cache_interfaces import CandleCacheable


class MockCandleCache:
    """Mock реализация CandleCacheable для тестов"""
    
    def __init__(self):
        self._candles = []
        self._current_price = None
    
    def add_candle(self, candle: Candle) -> None:
        self._candles.append(candle)
        self._current_price = candle.close.units + candle.close.nano / 1_000_000_000
    
    def get_latest_candles(self, count: int = 10) -> list:
        return self._candles[-count:]
    
    def get_current_price(self) -> float:
        return self._current_price
    
    def get_cached_candles(self) -> list:
        return self._candles
    
    def get_cache_size(self) -> int:
        return len(self._candles)
    
    def clear_cache(self) -> None:
        self._candles.clear()
        self._current_price = None
    
    @property
    def is_empty(self) -> bool:
        return len(self._candles) == 0
    
    @property
    def has_data(self) -> bool:
        return len(self._candles) > 0


def test_candle_cache_protocol_compliance():
    """Тест, что все реализации соответствуют протоколу CandleCacheable"""
    
    # Создаем тестовую свечу
    mock_candle = Mock(spec=Candle)
    mock_candle.close = MoneyValue(units=1000, nano=500000000)  # 1000.5
    mock_candle.time = Mock()
    
    # Тестируем стандартную реализацию
    standard_cache = CandleCache(cache_size=10)
    _test_cache_implementation(standard_cache, mock_candle, "CandleCache")
    
    # Тестируем mock реализацию
    mock_cache = MockCandleCache()
    _test_cache_implementation(mock_cache, mock_candle, "MockCandleCache")


def _test_cache_implementation(cache: CandleCacheable, candle: Candle, cache_name: str):
    """Вспомогательная функция для тестирования реализации кэша"""
    
    # Проверяем начальное состояние
    assert cache.is_empty, f"{cache_name}: кэш должен быть пустым в начале"
    assert not cache.has_data, f"{cache_name}: кэш не должен содержать данных в начале"
    assert cache.get_cache_size() == 0, f"{cache_name}: размер кэша должен быть 0"
    assert cache.get_current_price() is None, f"{cache_name}: текущая цена должна быть None"
    assert len(cache.get_latest_candles()) == 0, f"{cache_name}: список свечей должен быть пустым"
    
    # Добавляем свечу
    cache.add_candle(candle)
    
    # Проверяем состояние после добавления
    assert not cache.is_empty, f"{cache_name}: кэш не должен быть пустым после добавления свечи"
    assert cache.has_data, f"{cache_name}: кэш должен содержать данные после добавления свечи"
    assert cache.get_current_price() == 1000.5, f"{cache_name}: текущая цена должна быть 1000.5"
    
    # Очищаем кэш
    cache.clear_cache()
    
    # Проверяем состояние после очистки
    assert cache.is_empty, f"{cache_name}: кэш должен быть пустым после очистки"
    assert not cache.has_data, f"{cache_name}: кэш не должен содержать данных после очистки"
    assert cache.get_cache_size() == 0, f"{cache_name}: размер кэша должен быть 0 после очистки"
    assert cache.get_current_price() is None, f"{cache_name}: текущая цена должна быть None после очистки"


def test_protocol_flexibility():
    """Тест демонстрирует гибкость использования протокола"""
    
    # Функция, которая работает с любым кэшем, реализующим протокол
    def process_candles(cache: CandleCacheable, candles: list):
        """Обрабатывает свечи через любой кэш"""
        for candle in candles:
            cache.add_candle(candle)
        
        return {
            'cache_size': cache.get_cache_size(),
            'current_price': cache.get_current_price(),
            'latest_candles': cache.get_latest_candles(5),
            'has_data': cache.has_data
        }
    
    # Создаем тестовые свечи
    candles = []
    for i in range(3):
        candle = Mock(spec=Candle)
        candle.close = MoneyValue(units=1000 + i, nano=0)
        candle.time = Mock()
        candles.append(candle)
    
    # Тестируем с разными реализациями кэша
    implementations = [
        CandleCache(cache_size=10),
        MockCandleCache(),
    ]
    
    for cache in implementations:
        result = process_candles(cache, candles)
        
        # Проверяем, что функция работает с любой реализацией
        assert result['cache_size'] >= 0
        assert result['current_price'] is not None
        assert isinstance(result['latest_candles'], list)
        assert isinstance(result['has_data'], bool)


if __name__ == "__main__":
    pytest.main([__file__])
