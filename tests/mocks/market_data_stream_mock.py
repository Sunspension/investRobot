"""
Мок для потока рыночных данных
"""
from typing import List, Optional
from collections import deque
from unittest.mock import Mock
from tinkoff.invest import Candle


class MockMarketDataStream:
    """Мок для потока рыночных данных"""
    
    def __init__(self, **kwargs):
        self._callbacks = []
        self._running = False
        self._candles = kwargs.get('candles', [])
        self._cached_candles = deque(maxlen=kwargs.get('cache_size', 100))
        self._current_price = kwargs.get('current_price', None)
        
        # Инициализируем кэш тестовыми данными
        for candle in self._candles:
            self._cached_candles.append(candle)
    
    def add_signal_callback(self, callback) -> None:
        """Добавляет колбэк для обработки сигналов"""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Запускает поток данных"""
        self._running = True
        # В реальном тесте здесь можно симулировать получение данных
    
    async def stop(self) -> None:
        """Останавливает поток данных"""
        self._running = False
    
    async def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """Возвращает последние N свечей из кэша"""
        if not self._cached_candles:
            return []
        return list(self._cached_candles)[-count:]
    
    async def get_current_price(self) -> Optional[float]:
        """Возвращает текущую цену"""
        return self._current_price
    
    def get_cached_candles(self) -> List[Candle]:
        """Возвращает все кэшированные свечи"""
        return list(self._cached_candles)
    
    def get_cache_size(self) -> int:
        """Возвращает размер кэша"""
        return len(self._cached_candles)
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        self._cached_candles.clear()
        self._current_price = None
    
    def add_candle_callback(self, callback) -> None:
        """Добавляет колбэк для свечей"""
        self._callbacks.append(callback)
    
    def remove_candle_callback(self, callback) -> None:
        """Удаляет колбэк для свечей"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def remove_signal_callback(self, callback) -> None:
        """Удаляет колбэк для сигналов"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
