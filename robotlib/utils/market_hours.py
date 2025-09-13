"""
Модуль для проверки торговых часов через Tinkoff API
"""
import pytz
from datetime import datetime
from typing import Optional
import asyncio

# Импорты для API функций
try:
    from robotlib.utils.tinkoff_market_hours import get_market_status_api, is_trading_time_api
    HAS_API = True
except ImportError:
    HAS_API = False


def check_market_open() -> bool:
    """
    Быстрая проверка, открыта ли биржа через API
    
    Returns:
        True если биржа открыта, False иначе
    """
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(is_trading_time_api())
    finally:
        loop.close()


def get_market_status() -> dict:
    """
    Получает статус рынка через API
    
    Returns:
        Словарь с информацией о статусе рынка
    """
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(get_market_status_api())
    finally:
        loop.close()


async def get_market_status_with_api(dt: Optional[datetime] = None) -> dict:
    """
    Получает статус рынка через Tinkoff API
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        Словарь с информацией о статусе рынка
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
    """
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    return await is_trading_time_api(dt)


# Пример использования
async def main():
    """Пример использования"""
    print("🧪 Тестирование торговых часов через API")
    print("=" * 50)
    
    if not HAS_API:
        print("❌ Tinkoff API недоступен. Торговля невозможна без API.")
        return
    
    # Тестирование
    status = get_market_status()
    print(f"Текущее время: {status['current_time']}")
    print(f"Биржа открыта: {status['is_trading']}")
    
    # Информация о торговом расписании через API
    try:
        from robotlib.utils.tinkoff_market_hours import TinkoffMarketHours
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            market_hours = TinkoffMarketHours(token="your_token", sandbox=True)
            schedule = loop.run_until_complete(market_hours.get_trading_schedule())
            print(f"\nТорговое расписание получено через API для {len(schedule['days'])} дней")
        finally:
            loop.close()
    except Exception as e:
        print(f"\nОшибка получения расписания: {e}")
    
    if status['next_session']:
        print(f"\nСледующая сессия: {status['next_session']['session']['name']}")
        print(f"Начало: {status['next_session']['start']}")
        print(f"Конец: {status['next_session']['end']}")


if __name__ == "__main__":
    asyncio.run(main())
