"""
Интерфейсы для кэша свечей
"""
from typing import Protocol, List, Optional
from tinkoff.invest import Candle


class CandleCacheable(Protocol):
    """Протокол для кэша свечей"""
    
    def add_candle(self, candle: Candle) -> None:
        """Добавляет свечу в кэш"""
        ...
    
    def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """Возвращает последние N свечей из кэша"""
        ...
    
    def get_current_price(self) -> Optional[float]:
        """Возвращает текущую цену"""
        ...
    
    def get_cached_candles(self) -> List[Candle]:
        """Возвращает все кэшированные свечи"""
        ...
    
    def get_cache_size(self) -> int:
        """Возвращает размер кэша"""
        ...
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        ...
    
    @property
    def is_empty(self) -> bool:
        """Проверяет, пуст ли кэш"""
        ...
    
    @property
    def has_data(self) -> bool:
        """Проверяет, есть ли данные в кэше"""
        ...
