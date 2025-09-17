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


