"""
Модуль для загрузки исторических данных
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from tinkoff.invest import Candle, CandleInterval
from robotlib.trading.interfaces import TinkoffAPIClientable
from robotlib.trading.historical_data_loader_interfaces import HistoricalDataLoaderable
from robotlib.trading_interfaces import CandleEventSinkable
from robotlib.utils.logger import get_logger
from robotlib.utils.money import Money
from robotlib.utils.tinkoff_market_hours import get_tinkoff_market_hours
import pytz


class HistoricalDataLoader:
    """Класс для загрузки исторических данных и gap-fill"""
    
    def __init__(self, api_client: TinkoffAPIClientable, figi: str):
        """
        Инициализация загрузчика исторических данных
        
        Args:
            api_client: API клиент для получения данных
            figi: FIGI инструмента
        """
        self._api_client = api_client
        self._figi = figi
        self._logger = get_logger(__name__)
    
    async def load_historical_data(self, from_date: datetime, to_date: datetime) -> List[Candle]:
        """
        Загружает исторические данные за указанный период
        
        Args:
            from_date: Начальная дата
            to_date: Конечная дата
            
        Returns:
            Список исторических свечей
        """
        try:
            self._logger.info(f"Загрузка исторических данных: {from_date} - {to_date}")
            
            # Получаем исторические свечи
            candles_response = await self._api_client.get_candles(
                figi=self._figi,
                from_date=from_date,
                to_date=to_date,
                interval=CandleInterval.CANDLE_INTERVAL_1_MIN
            )
            
            if candles_response and candles_response.candles:
                self._logger.info(f"Загружено {len(candles_response.candles)} исторических свечей")
                
                # Логируем период данных для отладки
                if candles_response.candles:
                    first_candle = candles_response.candles[0]
                    last_candle = candles_response.candles[-1]
                    self._logger.info(f"Период данных: {first_candle.time} - {last_candle.time}")
                
                return candles_response.candles
            else:
                self._logger.debug(f"Пустой ответ от API (возможно, рынок закрыт или нет данных). Ответ: {candles_response}")
                return []
                
        except Exception as e:
            self._logger.error(f"Ошибка загрузки исторических данных: {e}")
            return []
    
    async def gap_fill_missing_candles(
        self, 
        last_candle_time: datetime, 
        sink: Optional[object] = None
    ) -> List[Candle]:
        """
        Дозагружает недостающие свечи с момента последней полученной до текущего времени
        
        Args:
            last_candle_time: Время последней полученной свечи
            sink: Приемник для отправки свечей (опционально)
            
        Returns:
            Список дозагруженных свечей
        """
        try:
            if last_candle_time is None:
                return []
            
            # Нормализуем к aware-UTC и сдвигаем старт на +1с, чтобы избежать дубликата
            from_time = last_candle_time
            if getattr(from_time, 'tzinfo', None) is None:
                from_time = from_time.replace(tzinfo=timezone.utc)
            else:
                from_time = from_time.astimezone(timezone.utc)
            from_time = from_time + timedelta(seconds=1)
            to_time = datetime.now(timezone.utc)
            
            # Защитимся от некорректного порядка
            if to_time <= from_time:
                return []
            
            candles = await self.load_historical_data(from_time, to_time)
            
            if candles and sink is not None:
                # Отправляем свечи в sink
                for candle in candles:
                    try:
                        # Расчет цены как в stream-пути
                        from robotlib.utils.money import Money
                        price = Money(candle.close).to_float()
                    except Exception:
                        try:
                            price = Money(candle.close).to_float()
                        except Exception:
                            price = 0.0
                    
                    if hasattr(sink, 'on_candle'):
                        asyncio.create_task(sink.on_candle(candle, price, self._figi))
            
            if candles:
                self._logger.info(f"Gap-fill: дозагружено {len(candles)} свечей с {from_time} по {to_time}")
            
            return candles
            
        except Exception as e:
            self._logger.warning(f"Gap-fill: ошибка дозагрузки свечей: {e}")
            return []
    
    async def get_last_main_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней основной торговой сессии (10:00-18:45)
        
        Returns:
            tuple: (from_date, to_date) - период последней основной торговой сессии
        """
        try:
            market_hours = await get_tinkoff_market_hours()
            schedule = await market_hours.get_trading_schedule()
            
            # Получаем текущую дату
            current_date = datetime.now(market_hours.moscow_tz).date()
            
            # Ищем последний торговый день
            last_trading_day = None
            for i in range(7):  # Проверяем последние 7 дней
                check_date = current_date - timedelta(days=i)
                date_str = check_date.isoformat()
                
                # Проверяем разные форматы дат
                search_keys = [
                    f"{date_str}T00:00:00+00:00",
                    date_str
                ]
                
                for key in search_keys:
                    if key in schedule['days']:
                        day_info = schedule['days'][key]
                        if day_info['is_trading_day'] and day_info['sessions']:
                            last_trading_day = day_info
                            break
                
                if last_trading_day:
                    break
            
            if last_trading_day and last_trading_day['sessions']:
                # Берем основную сессию (первую) - 10:00-18:45
                main_session = last_trading_day['sessions'][0]
                
                # Конвертируем время в московское
                if main_session['start'].tzinfo:
                    session_start = main_session['start'].astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].astimezone(market_hours.moscow_tz)
                else:
                    session_start = market_hours.moscow_tz.localize(main_session['start'])
                    session_end = market_hours.moscow_tz.localize(main_session['end'])
                
                # Для фьючерсов используем только основную сессию (10:00-18:45)
                session_date = session_start.date()
                from_date = market_hours.moscow_tz.localize(
                    datetime.combine(session_date, datetime.min.time().replace(hour=10, minute=0))
                )
                to_date = market_hours.moscow_tz.localize(
                    datetime.combine(session_date, datetime.min.time().replace(hour=18, minute=45))
                )
                
                self._logger.info(f"Основная сессия для фьючерса: {from_date} - {to_date}")
                return from_date, to_date
            else:
                # Если не найдена торговая сессия, используем стандартное время MOEX
                self._logger.warning("Не найдена торговая сессия, используем стандартное время MOEX (10:00-18:45)")
                yesterday = current_date - timedelta(days=1)
                from_date = market_hours.moscow_tz.localize(
                    datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0))
                )
                to_date = market_hours.moscow_tz.localize(
                    datetime.combine(yesterday, datetime.min.time().replace(hour=18, minute=45))
                )
                return from_date, to_date
                
        except Exception as e:
            self._logger.error(f"Ошибка определения периода основной сессии: {e}")
            # Fallback на вчерашний день
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = moscow_tz.localize(datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)))
            to_date = moscow_tz.localize(datetime.combine(yesterday, datetime.min.time().replace(hour=18, minute=45)))
            return from_date, to_date
    
    async def get_last_trading_session_period(self) -> Tuple[datetime, datetime]:
        """
        Определяет период последней торговой сессии
        
        Returns:
            tuple: (from_date, to_date) - период последней торговой сессии
        """
        try:
            market_hours = await get_tinkoff_market_hours()
            schedule = await market_hours.get_trading_schedule()
            
            # Получаем текущую дату
            current_date = datetime.now(market_hours.moscow_tz).date()
            
            # Ищем последний торговый день
            last_trading_day = None
            for i in range(7):  # Проверяем последние 7 дней
                check_date = current_date - timedelta(days=i)
                date_str = check_date.isoformat()
                
                # Проверяем разные форматы дат
                search_keys = [
                    f"{date_str}T00:00:00+00:00",
                    date_str
                ]
                
                for key in search_keys:
                    if key in schedule['days']:
                        day_info = schedule['days'][key]
                        if day_info['is_trading_day'] and day_info['sessions']:
                            last_trading_day = day_info
                            break
                
                if last_trading_day:
                    break
            
            if last_trading_day and last_trading_day['sessions']:
                # Берем основную сессию (первую)
                main_session = last_trading_day['sessions'][0]
                
                # Конвертируем время в московское
                if main_session['start'].tzinfo:
                    session_start = main_session['start'].astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].astimezone(market_hours.moscow_tz)
                else:
                    session_start = main_session['start'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                    session_end = main_session['end'].replace(tzinfo=timezone.utc).astimezone(market_hours.moscow_tz)
                
                self._logger.info(f"Найдена последняя торговая сессия: {session_start} - {session_end}")
                return session_start, session_end
            else:
                # Если не нашли торговую сессию, используем стандартное время торговой сессии MOEX
                yesterday = current_date - timedelta(days=1)
                # Стандартное время торговой сессии MOEX: 10:00 - 23:50 МСК (основная + вечерняя)
                from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=market_hours.moscow_tz)
                to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=market_hours.moscow_tz)
                self._logger.warning("Не найдена торговая сессия, используем стандартное время MOEX (10:00-23:50)")
                return from_date, to_date
                
        except Exception as e:
            self._logger.error(f"Ошибка определения периода последней сессии: {e}")
            # Fallback: используем стандартное время торговой сессии MOEX
            moscow_tz = pytz.timezone('Europe/Moscow')
            yesterday = datetime.now(moscow_tz).date() - timedelta(days=1)
            from_date = datetime.combine(yesterday, datetime.min.time().replace(hour=10, minute=0)).replace(tzinfo=moscow_tz)
            to_date = datetime.combine(yesterday, datetime.min.time().replace(hour=23, minute=50)).replace(tzinfo=moscow_tz)
            self._logger.warning("Fallback: используем стандартное время MOEX (10:00-23:50)")
            return from_date, to_date
