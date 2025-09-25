"""
Модуль для управления кэшем свечей
"""
from typing import List, Optional
from collections import deque
from tinkoff.invest import Candle
from robotlib.utils.logger import get_logger
from robotlib.trading.candle_cache_interfaces import CandleCacheable


class CandleCache:
    """Класс для управления кэшем свечей и текущей ценой"""
    
    def __init__(self, cache_size: int = 100):
        """
        Инициализация кэша свечей
        
        Args:
            cache_size: Максимальный размер кэша
        """
        self._cached_candles = deque(maxlen=cache_size)
        self._current_price: Optional[float] = None
        self._logger = get_logger(__name__)
    
    def add_candle(self, candle: Candle) -> None:
        """
        Добавляет свечу в кэш и обновляет текущую цену
        
        Args:
            candle: Свеча для добавления
        """
        try:
            self._cached_candles.append(candle)
            self._current_price = candle.close.units + candle.close.nano / 1_000_000_000
            self._logger.debug(f"Свеча добавлена в кэш: {candle.time} - {self._current_price}")
        except Exception as e:
            self._logger.error(f"Ошибка добавления свечи в кэш: {e}")
    
    def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """
        Возвращает последние N свечей из кэша
        
        Args:
            count: Количество свечей для возврата
            
        Returns:
            Список последних свечей
        """
        try:
            if not self._cached_candles:
                self._logger.warning("Кэш свечей пуст")
                return []
            
            # Возвращаем последние count свечей
            return list(self._cached_candles)[-count:]
            
        except Exception as e:
            self._logger.error(f"Ошибка получения последних свечей: {e}")
            return []
    
    def get_current_price(self) -> Optional[float]:
        """
        Возвращает текущую цену
        
        Returns:
            Текущая цена или None если данных нет
        """
        return self._current_price
    
    def get_cached_candles(self) -> List[Candle]:
        """
        Возвращает все кэшированные свечи
        
        Returns:
            Список всех кэшированных свечей
        """
        return list(self._cached_candles)
    
    def get_cache_size(self) -> int:
        """
        Возвращает размер кэша
        
        Returns:
            Количество свечей в кэше
        """
        return len(self._cached_candles)
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        self._cached_candles.clear()
        self._current_price = None
        self._logger.info("Кэш свечей очищен")
    
    @property
    def is_empty(self) -> bool:
        """Проверяет, пуст ли кэш"""
        return len(self._cached_candles) == 0
    
    @property
    def has_data(self) -> bool:
        """Проверяет, есть ли данные в кэше"""
        return len(self._cached_candles) > 0
