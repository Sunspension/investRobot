"""
Модуль для проверки торговых часов Московской биржи
"""
import pytz
from datetime import datetime, time, timedelta
from typing import Optional
import asyncio

# Импорты для API функций
try:
    from robotlib.utils.tinkoff_market_hours import get_market_status_api, is_trading_time_api
    HAS_API = True
except ImportError:
    HAS_API = False


class MarketHours:
    """Класс для проверки торговых часов Московской биржи"""
    
    # Московское время
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    
    # Торговые сессии для фьючерсов на индекс МосБиржи (будни)
    WEEKDAY_TRADING_SESSIONS = [
        # Аукцион открытия: 9:50 - 10:00 МСК
        {
            'start': time(9, 50),
            'end': time(10, 0),
            'name': 'Аукцион открытия'
        },
        # Основная сессия: 10:00 - 18:50 МСК
        {
            'start': time(10, 0),
            'end': time(18, 50),
            'name': 'Основная сессия'
        },
        # Вечерняя сессия: 19:05 - 23:50 МСК
        {
            'start': time(19, 5),
            'end': time(23, 50),
            'name': 'Вечерняя сессия'
        }
    ]
    
    # Торговые сессии для фьючерсов в выходные (суббота и воскресенье)
    WEEKEND_TRADING_SESSIONS = [
        # Аукцион открытия: 9:50 - 10:00 МСК
        {
            'start': time(9, 50),
            'end': time(10, 0),
            'name': 'Аукцион открытия (выходные)'
        },
        # Утренняя сессия: 10:00 - 14:00 МСК
        {
            'start': time(10, 0),
            'end': time(14, 0),
            'name': 'Утренняя сессия (выходные)'
        },
        # Вечерняя сессия: 19:05 - 23:50 МСК
        {
            'start': time(19, 5),
            'end': time(23, 50),
            'name': 'Вечерняя сессия (выходные)'
        }
    ]
    
    # Выходные дни (суббота и воскресенье) - но торговля есть!
    WEEKEND_DAYS = [5, 6]  # 5=суббота, 6=воскресенье
    
    @classmethod
    def is_trading_time(cls, dt: Optional[datetime] = None) -> bool:
        """
        Проверяет, идет ли сейчас торговая сессия
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            True если идет торговая сессия, False иначе
        """
        if dt is None:
            dt = datetime.now(cls.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = cls.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(cls.MOSCOW_TZ)
        
        current_time = dt.time()
        is_weekend = dt.weekday() in cls.WEEKEND_DAYS
        
        # Выбираем соответствующие торговые сессии
        if is_weekend:
            trading_sessions = cls.WEEKEND_TRADING_SESSIONS
        else:
            trading_sessions = cls.WEEKDAY_TRADING_SESSIONS
        
        # Проверяем торговые сессии
        for session in trading_sessions:
            if session['start'] <= current_time <= session['end']:
                return True
        
        return False
    
    @classmethod
    def get_next_trading_session(cls, dt: Optional[datetime] = None) -> dict:
        """
        Возвращает информацию о следующей торговой сессии
        
        Args:
            dt: Время для расчета (по умолчанию текущее время)
            
        Returns:
            Словарь с информацией о следующей сессии
        """
        if dt is None:
            dt = datetime.now(cls.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = cls.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(cls.MOSCOW_TZ)
        
        current_time = dt.time()
        current_date = dt.date()
        is_weekend = dt.weekday() in cls.WEEKEND_DAYS
        
        # Если сейчас торговая сессия
        if cls.is_trading_time(dt):
            # Выбираем соответствующие торговые сессии
            if is_weekend:
                trading_sessions = cls.WEEKEND_TRADING_SESSIONS
            else:
                trading_sessions = cls.WEEKDAY_TRADING_SESSIONS
            
            for session in trading_sessions:
                if session['start'] <= current_time <= session['end']:
                    return {
                        'session': session,
                        'start': dt.replace(
                            hour=session['start'].hour,
                            minute=session['start'].minute,
                            second=0,
                            microsecond=0
                        ),
                        'end': dt.replace(
                            hour=session['end'].hour,
                            minute=session['end'].minute,
                            second=0,
                            microsecond=0
                        ),
                        'is_current': True
                    }
        
        # Ищем следующую сессию
        for days_ahead in range(7):  # Проверяем на неделю вперед
            check_date = current_date + timedelta(days=days_ahead)
            check_dt = cls.MOSCOW_TZ.localize(
                datetime.combine(check_date, time(0, 0))
            )
            
            # Определяем торговые сессии для этого дня
            check_is_weekend = check_dt.weekday() in cls.WEEKEND_DAYS
            if check_is_weekend:
                check_sessions = cls.WEEKEND_TRADING_SESSIONS
            else:
                check_sessions = cls.WEEKDAY_TRADING_SESSIONS
            
            for session in check_sessions:
                session_start = check_dt.replace(
                    hour=session['start'].hour,
                    minute=session['start'].minute,
                    second=0,
                    microsecond=0
                )
                
                # Если это будущая сессия
                if session_start > dt:
                    session_end = check_dt.replace(
                        hour=session['end'].hour,
                        minute=session['end'].minute,
                        second=0,
                        microsecond=0
                    )
                    
                    return {
                        'session': session,
                        'start': session_start,
                        'end': session_end,
                        'is_current': False
                    }
        
        return None
    
    @classmethod
    def get_trading_schedule_info(cls, dt: Optional[datetime] = None) -> dict:
        """
        Получает подробную информацию о торговом расписании
        
        Args:
            dt: Дата для проверки (по умолчанию текущая дата)
            
        Returns:
            Словарь с информацией о торговом расписании
        """
        if dt is None:
            dt = datetime.now(cls.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = cls.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(cls.MOSCOW_TZ)
        
        is_weekend = dt.weekday() in cls.WEEKEND_DAYS
        day_name = dt.strftime('%A')
        
        if is_weekend:
            trading_sessions = cls.WEEKEND_TRADING_SESSIONS
            day_type = "выходной"
        else:
            trading_sessions = cls.WEEKDAY_TRADING_SESSIONS
            day_type = "рабочий"
        
        return {
            'date': dt.date(),
            'day_name': day_name,
            'day_type': day_type,
            'is_weekend': is_weekend,
            'trading_sessions': trading_sessions,
            'is_trading_day': len(trading_sessions) > 0
        }
    
    @classmethod
    def get_trading_status(cls, dt: Optional[datetime] = None) -> dict:
        """
        Возвращает подробную информацию о торговом статусе
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            Словарь с информацией о торговом статусе
        """
        if dt is None:
            dt = datetime.now(cls.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = cls.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(cls.MOSCOW_TZ)
        
        is_trading = cls.is_trading_time(dt)
        next_session = cls.get_next_trading_session(dt)
        
        return {
            'is_trading': is_trading,
            'current_time': dt,
            'next_session': next_session,
            'time_until_next': (
                next_session['start'] - dt
            ).total_seconds() if next_session else None
        }


def check_market_open() -> bool:
    """
    Быстрая проверка, открыта ли биржа
    
    Returns:
        True если биржа открыта, False иначе
    """
    return MarketHours.is_trading_time()


def get_market_status() -> dict:
    """
    Получает статус рынка
    
    Returns:
        Словарь с информацией о статусе рынка
    """
    return MarketHours.get_trading_status()


async def get_market_status_with_api(dt: Optional[datetime] = None) -> dict:
    """
    Получает статус рынка через Tinkoff API
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        Словарь с информацией о статусе рынка
        
    Raises:
        Exception: Если API недоступен
    """
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    return await get_market_status_api(dt)


async def is_trading_time_with_api(dt: Optional[datetime] = None) -> bool:
    """
    Проверяет торговые часы через Tinkoff API
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        True если идет торговая сессия, False иначе
        
    Raises:
        Exception: Если API недоступен
    """
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    return await is_trading_time_api(dt)


if __name__ == "__main__":
    # Тестирование
    status = get_market_status()
    print(f"Текущее время: {status['current_time']}")
    print(f"Биржа открыта: {status['is_trading']}")
    
    # Информация о торговом расписании
    schedule_info = MarketHours.get_trading_schedule_info()
    print(f"\nТорговое расписание на {schedule_info['date']} ({schedule_info['day_name']}):")
    print(f"Тип дня: {schedule_info['day_type']}")
    print(f"Торговые сессии:")
    for session in schedule_info['trading_sessions']:
        print(f"  - {session['name']}: {session['start']} - {session['end']}")
    
    if status['next_session']:
        print(f"\nСледующая сессия: {status['next_session']['session']['name']}")
        print(f"Начало: {status['next_session']['start']}")
        print(f"Конец: {status['next_session']['end']}")
        
        if status['time_until_next']:
            hours = int(status['time_until_next'] // 3600)
            minutes = int((status['time_until_next'] % 3600) // 60)
            print(f"До начала: {hours}ч {minutes}м")
