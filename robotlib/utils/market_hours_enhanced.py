"""
Расширенный модуль для проверки торговых часов с поддержкой выходных торгов
"""
import pytz
from datetime import datetime, time
from typing import Optional, Dict, Any
import asyncio
from abc import ABC, abstractmethod

from robotlib.utils.logger import get_logger
from robotlib.utils.tinkoff_market_hours import get_market_status_api, is_trading_time_api


class MarketHoursProvidable(ABC):
    """Интерфейс для провайдера торговых часов"""
    
    @abstractmethod
    async def get_market_status(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Получает статус рынка"""
        pass
    
    @abstractmethod
    async def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """Проверяет торговое время"""
        pass


class TinkoffMarketHoursProvider(MarketHoursProvidable):
    """Провайдер торговых часов через Tinkoff API"""
    
    def __init__(self, get_market_status_api_func, is_trading_time_api_func):
        self._logger = get_logger(__name__)
        self._get_market_status_api = get_market_status_api_func
        self._is_trading_time_api = is_trading_time_api_func
    
    async def get_market_status(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Получает статус рынка через Tinkoff API"""
        return await self._get_market_status_api(dt)
    
    async def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """Проверяет торговое время через Tinkoff API"""
        return await self._is_trading_time_api(dt)


class MockMarketHoursProvider(MarketHoursProvidable):
    """Мок-провайдер торговых часов для тестирования"""
    
    def __init__(self):
        self._logger = get_logger(__name__)
    
    async def get_market_status(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Возвращает моковый статус рынка"""
        return {
            'is_trading': False,
            'current_time': dt or datetime.now(),
            'message': 'Моковый статус'
        }
    
    async def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """Возвращает моковое торговое время"""
        return False


class MarketHoursProviderFactory:
    """Фабрика для создания провайдеров торговых часов"""
    
    @staticmethod
    def create_tinkoff_provider() -> MarketHoursProvidable:
        """Создает провайдер Tinkoff API"""
        return TinkoffMarketHoursProvider(get_market_status_api, is_trading_time_api)
    
    @staticmethod
    def create_mock_provider() -> MarketHoursProvidable:
        """Создает мок-провайдер для тестирования"""
        return MockMarketHoursProvider()


class EnhancedMarketHours:
    """Расширенный класс для проверки торговых часов с поддержкой выходных торгов"""
    
    def __init__(self, market_hours_provider: MarketHoursProvidable):
        self._moscow_tz = pytz.timezone('Europe/Moscow')
        self._logger = get_logger(__name__)
        self._market_hours_provider = market_hours_provider
    
    def _is_weekend_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """
        Проверяет, идет ли выходная торговая сессия
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            True если идет выходная торговая сессия, False иначе
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        # Проверяем день недели
        weekday = dt.weekday()  # 0=понедельник, 6=воскресенье
        
        # Выходные торги: суббота (5) и воскресенье (6)
        if weekday not in [5, 6]:
            return False
        
        # Время выходных торгов: 10:00 - 18:00 МСК
        trading_start = time(10, 0)
        trading_end = time(18, 0)
        current_time = dt.time()
        
        return trading_start <= current_time <= trading_end
    
    def _is_evening_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """
        Проверяет, идет ли вечерняя торговая сессия
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            True если идет вечерняя торговая сессия, False иначе
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        # Вечерняя сессия: 19:05 - 23:50 МСК (с учетом клиринга 18:50-19:05)
        evening_start = time(19, 5)
        evening_end = time(23, 50)
        current_time = dt.time()
        
        return evening_start <= current_time <= evening_end
    
    async def is_trading_time_enhanced(self, dt: Optional[datetime] = None) -> bool:
        """
        Расширенная проверка торговых часов с поддержкой выходных и вечерних торгов
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            True если идет торговая сессия, False иначе
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        # 1. Проверяем через API (основные торговые часы)
        try:
            api_result = await self._market_hours_provider.is_trading_time(dt)
            if api_result:
                return True
        except Exception as e:
            self._logger.warning(f"Ошибка проверки через API: {e}")
        
        # 2. Проверяем выходные торги
        if self._is_weekend_trading_time(dt):
            return True
        
        # 3. Проверяем вечерние торги
        if self._is_evening_trading_time(dt):
            return True
        
        return False
    
    async def get_market_status_enhanced(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Расширенный статус рынка с поддержкой выходных и вечерних торгов
        
        Args:
            dt: Время для проверки (по умолчанию текущее время)
            
        Returns:
            Словарь со статусом рынка
        """
        if dt is None:
            dt = datetime.now(self._moscow_tz)
        elif dt.tzinfo is None:
            dt = self._moscow_tz.localize(dt)
        else:
            dt = dt.astimezone(self._moscow_tz)
        
        # Проверяем торговое время
        is_trading = await self.is_trading_time_enhanced(dt)
        
        # Определяем тип торговой сессии
        session_type = "closed"
        if is_trading:
            if self._is_weekend_trading_time(dt):
                session_type = "weekend"
            elif self._is_evening_trading_time(dt):
                session_type = "evening"
            else:
                session_type = "main"
        
        # Получаем базовый статус через API
        base_status = {}
        try:
            base_status = await self._market_hours_provider.get_market_status(dt)
        except Exception as e:
            self._logger.warning(f"Ошибка получения статуса через API: {e}")
        
        # Формируем расширенный статус
        enhanced_status = {
            'is_trading': is_trading,
            'current_time': dt,
            'session_type': session_type,
            'is_weekend_trading': self._is_weekend_trading_time(dt),
            'is_evening_trading': self._is_evening_trading_time(dt),
            'message': self._get_status_message(session_type, is_trading)
        }
        
        # Добавляем информацию из API, если доступна
        if base_status:
            enhanced_status.update({
                'next_session': base_status.get('next_session'),
                'time_until_next': base_status.get('time_until_next')
            })
        
        return enhanced_status
    
    def _get_status_message(self, session_type: str, is_trading: bool) -> str:
        """Возвращает сообщение о статусе рынка"""
        if not is_trading:
            return "Рынок закрыт"
        
        messages = {
            'main': "Основная торговая сессия",
            'evening': "Вечерняя торговая сессия",
            'weekend': "Выходная торговая сессия"
        }
        
        return messages.get(session_type, "Торговая сессия")


def create_enhanced_market_hours() -> EnhancedMarketHours:
    """Создает экземпляр EnhancedMarketHours с Tinkoff провайдером"""
    provider = MarketHoursProviderFactory.create_tinkoff_provider()
    return EnhancedMarketHours(provider)

def create_mock_enhanced_market_hours() -> EnhancedMarketHours:
    """Создает экземпляр EnhancedMarketHours с мок-провайдером для тестирования"""
    provider = MarketHoursProviderFactory.create_mock_provider()
    return EnhancedMarketHours(provider)


async def is_trading_time_enhanced(dt: Optional[datetime] = None) -> bool:
    """
    Быстрая проверка торговых часов с поддержкой выходных торгов
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        True если идет торговая сессия, False иначе
    """
    market_hours = create_enhanced_market_hours()
    return await market_hours.is_trading_time_enhanced(dt)


async def get_market_status_enhanced(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Расширенный статус рынка с поддержкой выходных торгов
    
    Args:
        dt: Время для проверки (по умолчанию текущее время)
        
    Returns:
        Словарь со статусом рынка
    """
    market_hours = create_enhanced_market_hours()
    return await market_hours.get_market_status_enhanced(dt)


# Пример использования
async def main():
    """Пример использования EnhancedMarketHours"""
    print("🧪 Тестирование расширенных торговых часов")
    print("=" * 50)
    
    # Тестирование
    status = await get_market_status_enhanced()
    print(f"Текущее время: {status['current_time']}")
    print(f"Рынок открыт: {status['is_trading']}")
    print(f"Тип сессии: {status['session_type']}")
    print(f"Выходные торги: {status['is_weekend_trading']}")
    print(f"Вечерние торги: {status['is_evening_trading']}")
    print(f"Сообщение: {status['message']}")


if __name__ == "__main__":
    asyncio.run(main())
