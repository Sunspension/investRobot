from abc import ABC, abstractmethod
from typing import List
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent
from tinkoff.invest import Candle, HistoricCandle


class Strategyable(ABC):
    """
    Базовый интерфейс для всех торговых стратегий.
    Все стратегии должны реализовывать этот интерфейс.
    """
    
    @property
    def income(self) -> float:
        """Возвращает текущий доход стратегии"""
        return getattr(self, '_income', 0.0)
    
    @property
    def position(self) -> int:
        """Возвращает текущую позицию стратегии"""
        return getattr(self, '_position', 0)
    
    @abstractmethod
    def execute(self, signal: Signal) -> List[OrderIntent]:
        """
        Выполняет торговую логику на основе сигнала.
        
        Args:
            signal: Торговый сигнал от SignalManager
            
        Returns:
            Список намерений на совершение сделок
        """
        pass
    
    @abstractmethod
    def close_position(self, candle: Candle | HistoricCandle) -> OrderIntent | None:
        """
        Закрывает все открытые позиции.
        
        Args:
            candle: Текущая свеча
            
        Returns:
            Намерение на закрытие позиции или None, если позиций нет
        """
        pass
