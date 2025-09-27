"""
Реестр стримов для переиспользования MarketDataStream
"""
from typing import Dict, Optional, Set
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.utils.logger import get_logger


class StreamRegistry:
    """Реестр для управления переиспользованием стримов"""
    
    def __init__(self):
        self._logger = get_logger(__name__)
        self._streams: Dict[str, MarketDataStream] = {}
        self._subscribers: Dict[str, Set[str]] = {}  # figi -> set of subscriber_ids
    
    def register_stream(self, figi: str, stream: MarketDataStream, subscriber_id: str) -> MarketDataStream:
        """
        Регистрирует стрим или возвращает существующий
        
        Args:
            figi: FIGI инструмента
            stream: Стрим для регистрации
            subscriber_id: ID подписчика
            
        Returns:
            Существующий или новый стрим
        """
        if figi in self._streams:
            self._logger.info(f"Переиспользуем существующий стрим для {figi}")
            # Добавляем подписчика
            if figi not in self._subscribers:
                self._subscribers[figi] = set()
            self._subscribers[figi].add(subscriber_id)
            return self._streams[figi]
        else:
            self._logger.info(f"Создаем новый стрим для {figi}")
            self._streams[figi] = stream
            self._subscribers[figi] = {subscriber_id}
            return stream
    
    def unregister_subscriber(self, figi: str, subscriber_id: str) -> bool:
        """
        Отписывает подписчика от стрима
        
        Args:
            figi: FIGI инструмента
            subscriber_id: ID подписчика
            
        Returns:
            True если стрим можно закрыть, False иначе
        """
        if figi not in self._subscribers:
            return False
            
        self._subscribers[figi].discard(subscriber_id)
        
        # Если подписчиков не осталось, можно закрыть стрим
        if not self._subscribers[figi]:
            self._logger.info(f"Нет подписчиков для {figi}, можно закрыть стрим")
            if figi in self._streams:
                del self._streams[figi]
            del self._subscribers[figi]
            return True
            
        return False
    
    def get_stream(self, figi: str) -> Optional[MarketDataStream]:
        """Получает существующий стрим"""
        return self._streams.get(figi)
    
    def has_stream(self, figi: str) -> bool:
        """Проверяет, есть ли стрим для FIGI"""
        return figi in self._streams
    
    def get_subscribers(self, figi: str) -> Set[str]:
        """Получает список подписчиков для FIGI"""
        return self._subscribers.get(figi, set())
    
    def get_all_streams(self) -> Dict[str, MarketDataStream]:
        """Получает все зарегистрированные стримы"""
        return self._streams.copy()
    
    def clear(self):
        """Очищает реестр"""
        self._streams.clear()
        self._subscribers.clear()
        self._logger.info("Реестр стримов очищен")


# Глобальный реестр
_stream_registry = StreamRegistry()


def get_stream_registry() -> StreamRegistry:
    """Получает глобальный реестр стримов"""
    return _stream_registry
