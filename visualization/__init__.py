#!/usr/bin/env python3
"""
Пакет визуализации торговых сигналов (новая Event-Driven архитектура)
Содержит модули для управления данными, построения графиков и UI
"""

# Основные компоненты визуализации
from .data_manager import DataManager
from .chart_builder import ChartBuilder
from .ui_components import UIComponents
from .event_visualizer_interface import EventVisualizerable, MockEventVisualizer
from .dash_event_visualizer import DashEventVisualizer
from .logging_config import disable_verbose_logging

__all__ = [
    'DataManager',
    'ChartBuilder', 
    'UIComponents',
    'EventVisualizerable',
    'MockEventVisualizer',
    'DashEventVisualizer',
    'disable_verbose_logging'
]