"""
Конфигурация для сервиса расчета размера позиции
"""
from dataclasses import dataclass


@dataclass
class PositionSizingConfig:
    """Конфигурация для динамического расчета размера позиции (фьючерсы).

    Основано на: волатильности (ATR), требовании ГО и состоянии системы/стратегии.
    Старые параметры риска на сделку, лимиты по портфелю, time/signal-strength удалены.
    """
    # Общие
    enable_dynamic_sizing: bool = True
    min_lots: int = 1                  # Минимальный размер заявки
    max_lots: int = 100                # Жесткий потолок лотов на сделку

    # Волатильность (ATR/цена) → чем выше, тем меньше размер
    volatility_threshold_high: float = 0.05
    volatility_threshold_medium: float = 0.02
    volatility_factor_high: float = 0.5      # при высокой волатильности
    volatility_factor_medium: float = 0.75   # при средней волатильности
    volatility_factor_low: float = 1.0       # при низкой волатильности

    # Состояние системы/стратегии: внешний мультипликатор [0..1]
    system_state_scale: float = 1.0

    # Оценка ГО, зарезервированного активными заявками (если недоступно из API)
    # Можно прокинуть через конфиг из внешнего слоя, иначе 0.
    active_orders_go_estimate: float = 0.0
