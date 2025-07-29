"""
Модуль для получения торговых часов через Tinkoff API
"""
import asyncio
import logging
from datetime import datetime, timedelta, time
from typing import Optional, Dict, Any, List
import pytz

from tinkoff.invest import AsyncClient, TradingSchedulesRequest
from config_data.config import load_config
from robotlib.utils.logger import get_logger


class TinkoffMarketHours:
    """Класс для получения торговых часов через Tinkoff API"""
    
    # Московское время
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    
    def __init__(self, token: str, sandbox: bool = True):
        """
        Инициализация
        
        Args:
            token: Токен доступа к API
            sandbox: Использовать песочницу
        """
        self.token = token
        self.sandbox = sandbox
        self.logger = get_logger(__name__)
        
        # Кэш расписаний
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
                    self.logger.debug("Используем кэшированное расписание")
                    return self._schedule_cache[cache_key]
            
            # Получаем расписание через API
            async with AsyncClient(token=self.token) as services:
                from_date = datetime.now(self.MOSCOW_TZ)
                to_date = from_date + timedelta(days=days_ahead)
                
                request = TradingSchedulesRequest(
                    exchange=exchange,
                    from_=from_date,
                    to=to_date
                )
                
                response = await services.instruments.trading_schedules(request=request)
                
                # Обрабатываем ответ
                schedule_data = self._process_schedule_response(response)
                
                # Сохраняем в кэш
                self._schedule_cache[cache_key] = schedule_data
                self._cache_timestamp = datetime.now()
                
                return schedule_data
                
        except Exception as e:
            self.logger.error(f"Ошибка получения торгового расписания: {e}")
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
            dt = datetime.now(self.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = self.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(self.MOSCOW_TZ)
        
        try:
            # Получаем расписание
            schedule = await self.get_trading_schedule(exchange)
            
            # Ищем день в расписании
            date_str = dt.date().isoformat()
            if date_str in schedule['days']:
                day_info = schedule['days'][date_str]
                if day_info['is_trading_day']:
                    current_time = dt.time()
                    
                    # Проверяем торговые сессии
                    for session in day_info['sessions']:
                        if session['start'] <= current_time <= session['end']:
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки торговых часов: {e}")
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
            dt = datetime.now(self.MOSCOW_TZ)
        elif dt.tzinfo is None:
            dt = self.MOSCOW_TZ.localize(dt)
        else:
            dt = dt.astimezone(self.MOSCOW_TZ)
        
        try:
            is_trading = await self.is_trading_time(dt)
            schedule = await self.get_trading_schedule()
            
            # Ищем следующую сессию
            next_session = self._find_next_session(dt, schedule)
            
            return {
                'is_trading': is_trading,
                'current_time': dt,
                'next_session': next_session,
                'time_until_next': (
                    next_session['start'] - dt
                ).total_seconds() if next_session else None
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса торгов: {e}")
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
                    
                    # Вечерняя сессия
                    if day.evening_start_time and day.evening_end_time:
                        sessions.append({
                            'name': 'Вечерняя сессия',
                            'start': day.evening_start_time,
                            'end': day.evening_end_time
                        })
                    
                    # Дополнительные сессии
                    if hasattr(day, 'premarket_start_time') and day.premarket_start_time:
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
        
        # Проверяем текущий день
        date_str = current_date.isoformat()
        if date_str in schedule['days']:
            day_info = schedule['days'][date_str]
            if day_info['is_trading_day']:
                for session in day_info['sessions']:
                    if session['start'] > current_time:
                        session_start = dt.replace(
                            hour=session['start'].hour,
                            minute=session['start'].minute,
                            second=0,
                            microsecond=0
                        )
                        session_end = dt.replace(
                            hour=session['end'].hour,
                            minute=session['end'].minute,
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
            
            if date_str in schedule['days']:
                day_info = schedule['days'][date_str]
                if day_info['is_trading_day'] and day_info['sessions']:
                    # Берем первую сессию дня
                    session = day_info['sessions'][0]
                    session_start = self.MOSCOW_TZ.localize(
                        datetime.combine(check_date, session['start'])
                    )
                    session_end = self.MOSCOW_TZ.localize(
                        datetime.combine(check_date, session['end'])
                    )
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
    


# Глобальный экземпляр для удобства
_tinkoff_market_hours: Optional[TinkoffMarketHours] = None


async def get_tinkoff_market_hours() -> TinkoffMarketHours:
    """
    Получает глобальный экземпляр TinkoffMarketHours
    
    Returns:
        Экземпляр TinkoffMarketHours
    """
    global _tinkoff_market_hours
    
    if _tinkoff_market_hours is None:
        config = load_config()
        _tinkoff_market_hours = TinkoffMarketHours(
            token=config.tcs_client.token,
            sandbox=True
        )
    
    return _tinkoff_market_hours


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
