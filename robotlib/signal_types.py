"""
Типы данных для сигналов
"""

from dataclasses import dataclass
from typing import Optional
from tinkoff.invest import Candle, HistoricCandle


@dataclass
class Signal:
    """Сигнал торговой стратегии"""
    macd: float = None
    signal: float = None
    histogram: float = None
    macd_prev: float = None
    signal_prev: float = None
    peak_detected: bool = False
    trough_detected: bool = False
    candle: Candle | HistoricCandle = None


@dataclass
class Order:
    """Старый класс Order - оставляем для обратной совместимости"""
    type: str = None
    price: float = None
    marker_price: float = None
    quantity: int = None
    date: Optional[str] = None
    profit: int = None
    
    def __str__(self):
        if self.profit is None:
            return f"Order(type='{self.type}', price={self.price}, marker_price={self.marker_price}, quantity={self.quantity}, date={self.date})"
        else:
            return f"Order(type='{self.type}', price={self.price}, marker_price={self.marker_price}, quantity={self.quantity}, date={self.date}, profit: {self.profit})"
