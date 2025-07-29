"""
Интерфейсы для компонентов торговой сессии
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional


class SessionStatsable(ABC):
    """Интерфейс для управления статистикой торговой сессии"""
    
    @abstractmethod
    def add_signal(self) -> None:
        """Добавляет обработанный сигнал"""
        pass
    
    @abstractmethod
    def add_successful_order(self, volume: float, profit: float = 0.0) -> None:
        """Добавляет успешный ордер"""
        pass
    
    @abstractmethod
    def add_failed_order(self, volume: float) -> None:
        """Добавляет неудачный ордер"""
        pass
    
    @abstractmethod
    def update_balance(self, new_balance: float) -> None:
        """Обновляет баланс и отслеживает просадки"""
        pass
    
    @abstractmethod
    def get_stats_dict(self) -> Dict[str, Any]:
        """Возвращает статистику в виде словаря"""
        pass
    
    @abstractmethod
    def print_stats(self) -> None:
        """Выводит статистику в консоль"""
        pass
    
    @abstractmethod
    def finish_session(self) -> None:
        """Завершает сессию"""
        pass
    
    @property
    @abstractmethod
    def start_time(self) -> datetime:
        """Время начала сессии"""
        pass
    
    @property
    @abstractmethod
    def end_time(self) -> Optional[datetime]:
        """Время окончания сессии"""
        pass
    
    @property
    @abstractmethod
    def total_signals(self) -> int:
        """Общее количество сигналов"""
        pass
    
    @property
    @abstractmethod
    def successful_orders(self) -> int:
        """Количество успешных ордеров"""
        pass
    
    @property
    @abstractmethod
    def failed_orders(self) -> int:
        """Количество неудачных ордеров"""
        pass
    
    @property
    @abstractmethod
    def total_volume(self) -> float:
        """Общий объем торгов"""
        pass
    
    @property
    @abstractmethod
    def total_profit(self) -> float:
        """Общая прибыль"""
        pass
    
    @property
    @abstractmethod
    def current_balance(self) -> float:
        """Текущий баланс"""
        pass


class SessionInitializable(ABC):
    """Интерфейс для инициализации компонентов торговой сессии"""
    
    @abstractmethod
    async def initialize_components(self) -> None:
        """Инициализирует все компоненты системы"""
        pass
    
    @abstractmethod
    async def initialize_strategies(self) -> None:
        """Инициализирует торговые стратегии"""
        pass
    
    @abstractmethod
    async def initialize_data_streams(self) -> None:
        """Инициализирует потоки данных"""
        pass
    
    @abstractmethod
    async def check_risk_limits(self) -> None:
        """Проверяет лимиты риска"""
        pass


class SessionControllable(ABC):
    """Интерфейс для управления жизненным циклом торговой сессии"""
    
    @abstractmethod
    async def start(self) -> bool:
        """Запускает торговую сессию"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Останавливает торговую сессию"""
        pass
    
    @abstractmethod
    async def run_trading_loop(self) -> None:
        """Запускает основной торговый цикл"""
        pass
    
    @abstractmethod
    async def get_session_status(self) -> Dict[str, Any]:
        """Возвращает статус сессии"""
        pass
    
    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Флаг работы сессии"""
        pass
    
    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        """Флаг инициализации сессии"""
        pass
    
    @property
    @abstractmethod
    def stats(self) -> SessionStatsable:
        """Статистика сессии"""
        pass


class TradingSessionable(ABC):
    """Интерфейс для торговой сессии"""
    
    @abstractmethod
    async def start(self) -> bool:
        """Запускает торговую сессию"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Останавливает торговую сессию"""
        pass
    
    @abstractmethod
    async def run_trading_loop(self) -> None:
        """Запускает основной торговый цикл"""
        pass
    
    @abstractmethod
    def get_stats(self) -> dict:
        """Возвращает статистику сессии"""
        pass
    
    @abstractmethod
    def print_stats(self) -> None:
        """Выводит статистику в консоль"""
        pass
    
    @abstractmethod
    async def execute_signal(self, signal) -> None:
        """Выполняет торговый сигнал"""
        pass
    
    @abstractmethod
    async def get_session_status(self) -> dict:
        """Возвращает статус сессии"""
        pass
    
    @abstractmethod
    async def close_all_positions(self) -> None:
        """Закрывает все позиции"""
        pass