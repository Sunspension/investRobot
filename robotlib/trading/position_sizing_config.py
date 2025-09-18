"""
Конфигурация для сервиса расчета размера позиции
"""
from dataclasses import dataclass


@dataclass
class PositionSizingConfig:
    """Конфигурация для динамического расчета размера позиции"""
    # Основные настройки
    enable_dynamic_sizing: bool = True    # Включить динамический расчет
    min_position_size: int = 1            # Минимальный размер позиции
    max_position_multiplier: float = 2.0  # Максимальный множитель от items_per_trade
    
    # Пороги волатильности (ATR/цена)
    volatility_threshold_high: float = 0.05   # Высокая волатильность
    volatility_threshold_medium: float = 0.02  # Средняя волатильность
    
    # Пороги силы сигнала (абсолютное значение гистограммы)
    signal_strength_threshold_strong: float = 0.3  # Сильный сигнал
    signal_strength_threshold_medium: float = 0.2  # Средний сигнал
    signal_strength_threshold_weak: float = 0.1   # Слабый сигнал
    
    # Коэффициенты для расчета
    volatility_factor_high: float = 0.5      # Коэффициент при высокой волатильности
    volatility_factor_medium: float = 0.8    # Коэффициент при средней волатильности
    volatility_factor_low: float = 1.2       # Коэффициент при низкой волатильности
    
    signal_factor_strong: float = 1.5        # Коэффициент при сильном сигнале
    signal_factor_medium: float = 1.2        # Коэффициент при среднем сигнале
    signal_factor_weak: float = 1.0          # Коэффициент при слабом сигнале
    signal_factor_very_weak: float = 0.7     # Коэффициент при очень слабом сигнале
    
    time_factor_close: float = 0.5           # Коэффициент перед закрытием
    time_factor_last_hour: float = 0.7       # Коэффициент в последний час
    time_factor_normal: float = 1.0          # Коэффициент в обычное время
    
    risk_factor_min: float = 0.7             # Минимальный коэффициент риска
    risk_factor_max: float = 1.0             # Максимальный коэффициент риска
