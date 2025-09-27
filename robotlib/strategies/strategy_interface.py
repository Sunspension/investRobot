from abc import ABC, abstractmethod
from typing import List, Optional
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderIntent
from robotlib.trading.position_sync_interface import PositionContext
from tinkoff.invest import Candle, HistoricCandle


class Strategyable(ABC):
    """
    Базовый интерфейс для всех торговых стратегий.
    Все стратегии должны реализовывать этот интерфейс.
    """
    
    
    @abstractmethod
    def execute(self, signal: Signal, position_context: PositionContext) -> List[OrderIntent]:
        """
        Выполняет торговую логику на основе сигнала.
        
        Args:
            signal: Торговый сигнал от SignalManager
            position_context: Контекст позиции для принятия решений
            
        Returns:
            Список намерений на совершение сделок
        """
        pass
    
