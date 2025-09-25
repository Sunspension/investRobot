"""
Интерфейсы для загрузчика исторических данных
"""
from typing import Protocol, List, Optional, Tuple
from datetime import datetime
from tinkoff.invest import Candle, CandleInterval
from robotlib.trading_interfaces import CandleEventSinkable


class HistoricalDataLoaderable(Protocol):
    """Протокол для загрузчика исторических данных"""
    
    async def load_historical_data(
        self, 
        from_date: datetime, 
        to_date: datetime
    ) -> List[Candle]:
        """
        Загружает исторические данные фиксированного окна до текущего момента (UTC)
        
        Args:
            from_date: Начальная дата
            to_date: Конечная дата
            
        Returns:
            Список свечей
        """
        ...
    
    async def gap_fill_missing_candles(
        self, 
        last_candle_time: datetime, 
        sink: Optional[CandleEventSinkable]
    ) -> None:
        """
        Дозагружает недостающие свечи с момента последней полученной до текущего времени.
        Публикует их через sink.on_candle, сохраняя семантику пайплайна.
        
        Args:
            last_candle_time: Время последней свечи
            sink: Приемник событий для публикации свечей
        """
        ...
    
    async def get_last_main_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней основной торговой сессии (10:00-18:45)
        
        Returns:
            Кортеж (начало_сессии, конец_сессии)
        """
        ...
    
    async def get_last_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней торговой сессии
        
        Returns:
            Кортеж (начало_сессии, конец_сессии)
        """
        ...
