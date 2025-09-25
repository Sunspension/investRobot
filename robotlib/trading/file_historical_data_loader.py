"""
Альтернативная реализация загрузчика исторических данных из файлов
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone, time
from typing import List, Optional, Tuple
from pathlib import Path
import pytz
from tinkoff.invest import Candle, CandleInterval

from robotlib.utils.logger import get_logger
from robotlib.trading.interfaces import TinkoffAPIClientable
from robotlib.trading.historical_data_loader_interfaces import HistoricalDataLoaderable
from robotlib.trading_interfaces import CandleEventSinkable


class FileHistoricalDataLoader:
    """Реализация загрузчика исторических данных из файлов (пример альтернативной реализации)"""
    
    def __init__(self, api_client: TinkoffAPIClientable, figi: str, data_dir: str = "data/historical"):
        """
        Инициализация загрузчика исторических данных из файлов
        
        Args:
            api_client: API клиент (для совместимости с протоколом)
            figi: FIGI инструмента
            data_dir: Директория с историческими данными
        """
        self._api_client = api_client
        self._figi = figi
        self._data_dir = Path(data_dir)
        self._logger = get_logger(__name__)
        
        # Создаем директорию если не существует
        self._data_dir.mkdir(parents=True, exist_ok=True)
    
    async def load_historical_data(
        self, 
        from_date: datetime, 
        to_date: datetime
    ) -> List[Candle]:
        """
        Загружает исторические данные из файлов
        
        Args:
            from_date: Начальная дата
            to_date: Конечная дата
            
        Returns:
            Список свечей
        """
        try:
            self._logger.info(f"Загрузка исторических данных из файлов: {from_date} - {to_date}")
            
            # В реальной реализации здесь была бы загрузка из файлов
            # Для демонстрации возвращаем пустой список
            candles = []
            
            # Пример логики загрузки из файлов:
            # for date in self._get_date_range(from_date, to_date):
            #     file_path = self._data_dir / f"{self._figi}_{date.strftime('%Y%m%d')}.json"
            #     if file_path.exists():
            #         with open(file_path, 'r') as f:
            #             data = json.load(f)
            #             candles.extend(self._parse_candles_from_json(data))
            
            self._logger.info(f"Загружено {len(candles)} свечей из файлов")
            return candles
            
        except Exception as e:
            self._logger.error(f"Ошибка загрузки исторических данных из файлов: {e}")
            return []
    
    async def gap_fill_missing_candles(
        self, 
        last_candle_time: datetime, 
        sink: Optional[CandleEventSinkable]
    ) -> None:
        """
        Дозагружает недостающие свечи из файлов
        
        Args:
            last_candle_time: Время последней свечи
            sink: Приемник событий для публикации свечей
        """
        try:
            if last_candle_time is None:
                return
            
            from_time = last_candle_time
            if getattr(from_time, 'tzinfo', None) is None:
                from_time = from_time.replace(tzinfo=timezone.utc)
            else:
                from_time = from_time.astimezone(timezone.utc)
            from_time = from_time + timedelta(seconds=1)
            to_time = datetime.now(timezone.utc)
            
            if to_time <= from_time:
                return
            
            # Загружаем данные из файлов
            candles = await self.load_historical_data(from_time, to_time)
            
            # Публикуем через sink
            for candle in candles:
                try:
                    price = float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9)
                except Exception:
                    price = 0.0
                
                if sink is not None:
                    asyncio.create_task(sink.on_candle(candle, price, self._figi))
            
            self._logger.info(f"Gap-fill из файлов: дозагружено {len(candles)} свечей с {from_time} по {to_time}")
            
        except Exception as e:
            self._logger.warning(f"Gap-fill из файлов: ошибка дозагрузки свечей: {e}")
    
    async def get_last_main_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней основной торговой сессии (10:00-18:45)
        
        Returns:
            Кортеж (начало_сессии, конец_сессии)
        """
        try:
            # В реальной реализации здесь была бы логика определения сессии
            # Для демонстрации используем стандартное время MOEX
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, time(10, 0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, time(18, 45)))
            
            self._logger.info(f"Основная сессия для фьючерса (из файлов): {from_date} - {to_date}")
            return from_date, to_date
            
        except Exception as e:
            self._logger.error(f"Ошибка определения периода основной сессии из файлов: {e}")
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, time(10, 0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, time(18, 45)))
            return from_date, to_date
    
    async def get_last_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней торговой сессии
        
        Returns:
            Кортеж (начало_сессии, конец_сессии)
        """
        try:
            # В реальной реализации здесь была бы логика определения сессии
            # Для демонстрации используем стандартное время MOEX
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, time(10, 0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, time(23, 50)))
            
            self._logger.info(f"Последняя торговая сессия (из файлов): {from_date} - {to_date}")
            return from_date, to_date
            
        except Exception as e:
            self._logger.error(f"Ошибка определения периода последней сессии из файлов: {e}")
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, time(10, 0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, time(23, 50)))
            return from_date, to_date
    
    def _get_date_range(self, start_date: datetime, end_date: datetime) -> List[datetime]:
        """Вспомогательный метод для получения диапазона дат"""
        dates = []
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            dates.append(datetime.combine(current_date, datetime.min.time()))
            current_date += timedelta(days=1)
        
        return dates
    
    def _parse_candles_from_json(self, data: dict) -> List[Candle]:
        """Вспомогательный метод для парсинга свечей из JSON"""
        # В реальной реализации здесь была бы логика парсинга
        return []
