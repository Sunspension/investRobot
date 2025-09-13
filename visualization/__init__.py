#!/usr/bin/env python3
"""
Пакет визуализации торговых сигналов
Содержит модули для управления данными, построения графиков и UI
"""

# Основные компоненты визуализации
from .data_manager import DataManager
from .chart_builder import ChartBuilder
from .ui_components import UIComponents
from .interfaces import (
    StrategyDataProvider, 
    TradingSessionDataProvider, 
    MockStrategyDataProvider,
    DataManagerable,
    ChartBuilderable,
    UIComponentsable
)
from .trading_visualizer_adapter import TradingVisualizerAdapter
from .logging_config import disable_verbose_logging

__all__ = [
    'DataManager',
    'ChartBuilder', 
    'UIComponents',
    'StrategyDataProvider',
    'TradingSessionDataProvider', 
    'MockStrategyDataProvider',
    'DataManagerable',
    'ChartBuilderable',
    'UIComponentsable',
    'TradingVisualizerAdapter',
    'disable_verbose_logging'
]
