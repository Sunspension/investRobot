"""
Класс для управления статистикой торговой сессии
"""
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from robotlib.trading.session_interfaces import SessionStatsable
from robotlib.utils.logger import get_logger


@dataclass
class SessionStats(SessionStatsable):
    """Статистика торговой сессии"""
    _start_time: datetime = field(default_factory=datetime.now)
    _end_time: Optional[datetime] = None
    _total_signals: int = 0
    _successful_orders: int = 0
    _failed_orders: int = 0
    _total_volume: float = 0.0
    _total_profit: float = 0.0
    _max_drawdown: float = 0.0
    _current_drawdown: float = 0.0
    _peak_balance: float = 0.0
    _current_balance: float = 0.0
    
    @property
    def start_time(self) -> datetime:
        return self._start_time
    
    @property
    def end_time(self) -> Optional[datetime]:
        return self._end_time
    
    @property
    def total_signals(self) -> int:
        return self._total_signals
    
    @property
    def successful_orders(self) -> int:
        return self._successful_orders
    
    @property
    def failed_orders(self) -> int:
        return self._failed_orders
    
    @property
    def total_volume(self) -> float:
        return self._total_volume
    
    @property
    def total_profit(self) -> float:
        return self._total_profit
    
    @property
    def current_balance(self) -> float:
        return self._current_balance
    
    @property
    def max_drawdown(self) -> float:
        return self._max_drawdown
    
    @property
    def current_drawdown(self) -> float:
        return self._current_drawdown
    
    @property
    def peak_balance(self) -> float:
        return self._peak_balance
    
    def __post_init__(self):
        self.logger = get_logger(__name__)
    
    def update_balance(self, new_balance: float) -> None:
        """Обновляет баланс и отслеживает просадки"""
        self._current_balance = new_balance
        
        if new_balance > self._peak_balance:
            self._peak_balance = new_balance
            self._current_drawdown = 0.0
        else:
            self._current_drawdown = self._peak_balance - new_balance
            if self._current_drawdown > self._max_drawdown:
                self._max_drawdown = self._current_drawdown
    
    def add_signal(self) -> None:
        """Добавляет обработанный сигнал"""
        self._total_signals += 1
    
    def add_successful_order(self, volume: float, profit: float = 0.0) -> None:
        """Добавляет успешный ордер"""
        self._successful_orders += 1
        self._total_volume += volume
        self._total_profit += profit
    
    def add_failed_order(self) -> None:
        """Добавляет неудачный ордер"""
        self._failed_orders += 1
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """Возвращает статистику в виде словаря"""
        duration = None
        if self._end_time:
            duration = (self._end_time - self._start_time).total_seconds()
        elif self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds()
        
        return {
            'start_time': self._start_time.isoformat(),
            'end_time': self._end_time.isoformat() if self._end_time else None,
            'duration_seconds': duration,
            'total_signals': self._total_signals,
            'successful_orders': self._successful_orders,
            'failed_orders': self._failed_orders,
            'success_rate': self._successful_orders / max(1, self._successful_orders + self._failed_orders),
            'total_volume': self._total_volume,
            'total_profit': self._total_profit,
            'max_drawdown': self._max_drawdown,
            'current_drawdown': self._current_drawdown,
            'peak_balance': self._peak_balance,
            'current_balance': self._current_balance
        }
    
    def print_stats(self) -> None:
        """Выводит статистику в консоль"""
        stats = self.get_stats_dict()
        
        self.logger.info("=== СТАТИСТИКА ТОРГОВОЙ СЕССИИ ===")
        self.logger.info(f"Время работы: {stats['duration_seconds']:.1f} сек")
        self.logger.info(f"Обработано сигналов: {stats['total_signals']}")
        self.logger.info(f"Успешных ордеров: {stats['successful_orders']}")
        self.logger.info(f"Неудачных ордеров: {stats['failed_orders']}")
        self.logger.info(f"Процент успеха: {stats['success_rate']:.1%}")
        self.logger.info(f"Общий объем: {stats['total_volume']:.2f}")
        self.logger.info(f"Общая прибыль: {stats['total_profit']:.2f}")
        self.logger.info(f"Максимальная просадка: {stats['max_drawdown']:.2f}")
        self.logger.info(f"Текущая просадка: {stats['current_drawdown']:.2f}")
        self.logger.info(f"Пиковый баланс: {stats['peak_balance']:.2f}")
        self.logger.info(f"Текущий баланс: {stats['current_balance']:.2f}")
    
    def finish_session(self) -> None:
        """Завершает сессию"""
        self._end_time = datetime.now()
        self.logger.info(f"Торговая сессия завершена в {self._end_time}")
