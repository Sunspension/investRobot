"""
Модуль для получения торговых часов через Tinkoff API
"""
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List, Union
import pytz

from tinkoff.invest import AsyncClient
from config_data.config import load_config
from robotlib.utils.logger import get_logger


def _has_attr(obj: Any, attr_name: str) -> bool:
    """Проверяет, есть ли у объекта атрибут (для объектов из внешних API)"""
    return hasattr(obj, attr_name) and getattr(obj, attr_name) is not None


class TinkoffMarketHours:
    """Класс для получения торговых часов через Tinkoff API"""
    
    def __init__(self, token: str, sandbox: bool = True):
        """
        Инициализация
        
        Args:
            token: Токен доступа к API
            sandbox: Использовать песочницу
        """
        # Приватные атрибуты
        self._token = token
        self._sandbox = sandbox
        self._logger = get_logger(__name__)
        self._moscow_tz = pytz.timezone('Europe/Moscow')
        
        # Приватные атрибуты для кэширования
        self._schedule_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 час
    
    async def get_trading_schedule(
        self, 
        exchange: str = "MOEX",
        days_ahead: int = 7
    ) -> Dict[str, Any]:
        """
        Получает торговое расписание через API
        
        Args:
            exchange: Биржа (по умолчанию MOEX)
            days_ahead: Количество дней вперед
            
        Returns:
            Словарь с расписанием торгов
        """
        try:
            # Проверяем кэш
            cache_key = f"{exchange}_{days_ahead}"
            if self._is_cache_valid():
                if cache_key in self._schedule_cache:
                    self._logger.debug("Используем кэшированное расписание")
                    return self._schedule_cache[cache_key]
            
            # Получаем расписание через API
            async with AsyncClient(token=self._token) as services:
                from_date = datetime.now(self._moscow_tz)
                to_date = from_date + timedelta(days=days_ahead)
                
                response = await services.instruments.trading_schedules(
                    exchange=exchange,
                    from_=from_date,
                    to=to_date
                )
                
                # Обрабатываем ответ
                schedule_data = self._process_schedule_response(response)
                
                # Сохраняем в кэш
                self._schedule_cache[cache_key] = schedule_data
                self._cache_timestamp = datetime.now()
                
                return schedule_data
                
        except Exception as e:
            self._logger.error(f"Ошибка получения торгового расписания: {e}")
            raise Exception(f"Не удалось получить торговое расписание через API: {e}")
    
    async def is_trading_time(
        self, 
        dt: Optional[datetime] = None,
        exchange: str = "MOEX"
    ) -> bool:
        """
        Проверяет, идет ли сейчас торговая сессия
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            exchange: Биржа
            
        Returns:
            True если идет торговая сессия, False иначе
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        try:
            # Получаем расписание
            schedule = await self.get_trading_schedule(exchange)
            
            # Ищем день в расписании (конвертируем в UTC для поиска)
            dt_utc = dt.astimezone(pytz.UTC)
            date_str = dt_utc.date().isoformat()
            
            # Пробуем разные форматы дат
            search_keys = [
                f"{date_str}T00:00:00+00:00",  # 2025-09-12T00:00:00+00:00 (основной формат API)
                date_str,  # 2025-09-12 (резервный)
                dt_utc.strftime("%Y-%m-%dT00:00:00+00:00")  # Альтернативный формат
            ]
            
            day_info = None
            for key in search_keys:
                if key in schedule['days']:
                    day_info = schedule['days'][key]
                    break
            
            if day_info:
                if day_info['is_trading_day']:
                    current_time = dt.time()
                    
                    # Проверяем торговые сессии
                    for session in day_info['sessions']:
                        # Конвертируем время сессии из UTC в московское
                        if hasattr(session['start'], 'tzinfo') and session['start'].tzinfo:
                            session_start = session['start'].astimezone(self._moscow_tz).time()
                            session_end = session['end'].astimezone(self._moscow_tz).time()
                        else:
                            # Если время без timezone, считаем его UTC
                            session_start = pytz.UTC.localize(session['start']).astimezone(self._moscow_tz).time()
                            session_end = pytz.UTC.localize(session['end']).astimezone(self._moscow_tz).time()
                        
                        if session_start <= current_time <= session_end:
                            return True
                    
                    # Дополнительная проверка для вечерней сессии MOEX
                    # Вечерняя сессия: 19:05 - 23:50 МСК (с учетом клиринга 18:50-19:05)
                    if day_info['sessions']:
                        main_session = day_info['sessions'][0]  # Основная сессия
                        if hasattr(main_session['end'], 'tzinfo') and main_session['end'].tzinfo:
                            main_end = main_session['end'].astimezone(self._moscow_tz).time()
                        else:
                            main_end = pytz.UTC.localize(main_session['end']).astimezone(self._moscow_tz).time()
                        
                        # Вечерняя сессия начинается в 19:05 (после клиринга)
                        evening_start = time(19, 5)
                        evening_end = time(23, 50)
                        
                        # Если основная сессия закончилась и время в диапазоне вечерней сессии
                        if current_time > main_end and evening_start <= current_time <= evening_end:
                            return True
            
            return False
            
        except Exception as e:
            self._logger.error(f"Ошибка проверки торговых часов: {e}")
            raise Exception(f"Не удалось получить торговые часы через API: {e}")
    
    async def get_trading_status(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Получает подробную информацию о торговом статусе
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            Словарь с информацией о статусе
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        try:
            is_trading = await self.is_trading_time(dt)
            schedule = await self.get_trading_schedule()
            
            # Ищем следующую сессию
            next_session = self._find_next_session(dt, schedule)
            self._logger.debug(f"Найдена следующая сессия: {next_session}")
            
            result = {
                'is_trading': is_trading,
                'current_time': dt,
                'next_session': next_session,
                'time_until_next': (
                    next_session['start'] - dt
                ).total_seconds() if next_session else None
            }
            
            return result
            
        except Exception as e:
            self._logger.error(f"Ошибка получения статуса торгов: {e}")
            return {
                'is_trading': False,
                'current_time': dt,
                'next_session': None,
                'time_until_next': None
            }
    
    def _process_schedule_response(self, response) -> Dict[str, Any]:
        """
        Обрабатывает ответ API с расписанием
        
        Args:
            response: Ответ от API
            
        Returns:
            Обработанные данные расписания
        """
        schedule_data = {
            'exchange': 'MOEX',
            'days': {},
            'last_updated': datetime.now()
        }
        
        for exchange in response.exchanges:
            for day in exchange.days:
                date_str = day.date.isoformat()
                
                sessions = []
                if day.is_trading_day:
                    # Основная сессия
                    if day.start_time and day.end_time:
                        sessions.append({
                            'name': 'Основная сессия',
                            'start': day.start_time,
                            'end': day.end_time
                        })
                    
                    # Вечерняя сессия (проверяем, что время не равно 1970-01-01)
                    if (day.evening_start_time and day.evening_end_time and 
                        day.evening_start_time.year > 1970 and day.evening_end_time.year > 1970):
                        sessions.append({
                            'name': 'Вечерняя сессия',
                            'start': day.evening_start_time,
                            'end': day.evening_end_time
                        })
                    
                    # Дополнительные сессии
                    if (_has_attr(day, 'premarket_start_time') and 
                        day.premarket_start_time.year > 1970 and day.premarket_end_time.year > 1970):
                        sessions.append({
                            'name': 'Премаркет',
                            'start': day.premarket_start_time,
                            'end': day.premarket_end_time
                        })
                
                schedule_data['days'][date_str] = {
                    'date': day.date,
                    'is_trading_day': day.is_trading_day,
                    'sessions': sessions
                }
        
        return schedule_data
    
    def _find_next_session(self, dt: datetime, schedule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Ищет следующую торговую сессию
        
        Args:
            dt: Текущее время
            schedule: Расписание торгов
            
        Returns:
            Информация о следующей сессии или None
        """
        current_date = dt.date()
        current_time = dt.time()
        
        self._logger.debug(f"Поиск следующей сессии для {current_date} {current_time}")
        self._logger.debug(f"Доступные дни в расписании: {list(schedule['days'].keys())}")
        
        # Проверяем текущий день
        date_str = current_date.isoformat()
        # Также проверяем формат с timezone
        date_str_tz = f"{date_str}T00:00:00+00:00"
        
        day_info = None
        if date_str in schedule['days']:
            day_info = schedule['days'][date_str]
        elif date_str_tz in schedule['days']:
            day_info = schedule['days'][date_str_tz]
            
        if day_info:
            if day_info['is_trading_day']:
                for session in day_info['sessions']:
                    # session['start']/['end'] приходят как datetime; сравниваем по времени суток (МСК)
                    if hasattr(session['start'], 'tzinfo') and session['start'].tzinfo:
                        session_start_time = session['start'].astimezone(self._moscow_tz).time()
                        session_end_time = session['end'].astimezone(self._moscow_tz).time()
                    else:
                        session_start_time = pytz.UTC.localize(session['start']).astimezone(self._moscow_tz).time()
                        session_end_time = pytz.UTC.localize(session['end']).astimezone(self._moscow_tz).time()

                    if session_start_time > current_time:
                        session_start = dt.replace(
                            hour=session_start_time.hour,
                            minute=session_start_time.minute,
                            second=0,
                            microsecond=0
                        )
                        session_end = dt.replace(
                            hour=session_end_time.hour,
                            minute=session_end_time.minute,
                            second=0,
                            microsecond=0
                        )
                        return {
                            'session': session,
                            'start': session_start,
                            'end': session_end,
                            'is_current': True
                        }
        
        # Ищем в следующих днях
        for days_ahead in range(1, 8):
            check_date = current_date + timedelta(days=days_ahead)
            date_str = check_date.isoformat()
            date_str_tz = f"{date_str}T00:00:00+00:00"
            
            day_info = None
            if date_str in schedule['days']:
                day_info = schedule['days'][date_str]
            elif date_str_tz in schedule['days']:
                day_info = schedule['days'][date_str_tz]
            
            if day_info:
                if day_info['is_trading_day'] and day_info['sessions']:
                    # Берем первую сессию дня
                    session = day_info['sessions'][0]
                    # session['start'] уже datetime, конвертируем в московское время
                    if hasattr(session['start'], 'tzinfo') and session['start'].tzinfo:
                        session_start = session['start'].astimezone(self._moscow_tz)
                        session_end = session['end'].astimezone(self._moscow_tz)
                    else:
                        session_start = pytz.UTC.localize(session['start']).astimezone(self._moscow_tz)
                        session_end = pytz.UTC.localize(session['end']).astimezone(self._moscow_tz)
                    return {
                        'session': session,
                        'start': session_start,
                        'end': session_end,
                        'is_current': False
                    }
        
        return None
    
    def _is_cache_valid(self) -> bool:
        """
        Проверяет валидность кэша
        
        Returns:
            True если кэш валиден, False иначе
        """
        if self._cache_timestamp is None:
            return False
        
        return (datetime.now() - self._cache_timestamp).total_seconds() < self._cache_ttl
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        Получает информацию о кэше (для отладки)
        
        Returns:
            Словарь с информацией о кэше
        """
        return {
            'cache_size': len(self._schedule_cache),
            'cache_timestamp': self._cache_timestamp,
            'cache_ttl': self._cache_ttl,
            'is_valid': self._is_cache_valid()
        }
    
    def clear_cache(self) -> None:
        """Очищает кэш расписаний"""
        self._schedule_cache.clear()
        self._cache_timestamp = None
    
    @property
    def token(self) -> str:
        """Получает токен доступа к API"""
        return self._token
    
    @property
    def sandbox(self) -> bool:
        """Получает флаг использования песочницы"""
        return self._sandbox
    
    @property
    def moscow_tz(self) -> pytz.timezone:
        """Получает московскую временную зону"""
        return self._moscow_tz
    


class TinkoffMarketHoursSingleton:
    """Синглтон для TinkoffMarketHours"""
    _instance: Optional['TinkoffMarketHours'] = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls) -> 'TinkoffMarketHours':
        """
        Получает единственный экземпляр TinkoffMarketHours
        
        Returns:
            Экземпляр TinkoffMarketHours
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    config = load_config()
                    # Определяем режим песочницы по наличию sandbox_token
                    # Если sandbox_token есть и не пустой - используем песочницу, иначе - реальный API
                    sandbox_mode = config.tcs_client.sandbox_token is not None and config.tcs_client.sandbox_token.strip() != ""
                    cls._instance = TinkoffMarketHours(
                        token=config.tcs_client.token,
                        sandbox=sandbox_mode
                    )
        return cls._instance


async def get_tinkoff_market_hours() -> TinkoffMarketHours:
    """
    Получает глобальный экземпляр TinkoffMarketHours
    
    Returns:
        Экземпляр TinkoffMarketHours
    """
    return await TinkoffMarketHoursSingleton.get_instance()


async def is_trading_time_api(dt: Optional[datetime] = None) -> bool:
    """
    Быстрая проверка торговых часов через API
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        True если идет торговая сессия, False иначе
    """
    market_hours = await get_tinkoff_market_hours()
    return await market_hours.is_trading_time(dt)


async def get_market_status_api(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Получает статус рынка через API
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        Словарь с информацией о статусе рынка
    """
    market_hours = await get_tinkoff_market_hours()
    return await market_hours.get_trading_status(dt)


# Пример использования
async def main():
    """Пример использования"""
    print("🧪 Тестирование TinkoffMarketHours")
    print("=" * 50)
    
    # Создаем экземпляр
    config = load_config()
    market_hours = TinkoffMarketHours(
        token=config.tcs_client.token,
        sandbox=True
    )
    
    # Проверяем текущее время
    is_trading = await market_hours.is_trading_time()
    print(f"Торговля идет: {is_trading}")
    
    # Получаем статус
    status = await market_hours.get_trading_status()
    print(f"Статус: {status}")
    
    # Получаем расписание
    schedule = await market_hours.get_trading_schedule()
    print(f"Расписание получено для {len(schedule['days'])} дней")


if __name__ == "__main__":
    asyncio.run(main())
