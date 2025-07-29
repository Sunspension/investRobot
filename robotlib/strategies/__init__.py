"""
Модули для торговых стратегий
"""
from .strategy_interface import Strategyable
from .strategy_manager import StrategyManager
from .long import LongStrategy
from .short import ShortStrategy

__all__ = [
    'Strategyable',
    'StrategyManager',
    'LongStrategy',
    'ShortStrategy'
]
