"""
Конфигурация для индивидуальной торговли по счёту
"""
from dataclasses import dataclass
from typing import Optional, List
from datetime import time


@dataclass
class AccountConfig:
    """Конфигурация для одного торгового счёта"""
    
    account_id: str
    token: str
    sandbox_token: str
    
    # Параметры торговли
    figi: str = "FUTIMOEXF000"
    deposit: float = 100000.0
    
    # Управление рисками
    max_daily_loss: float = 5000.0
    max_position_size: float = 50000.0
    stop_loss_threshold: float = 2.0
    
    # Настройки сессии
    auto_close_positions: bool = True
    end_of_day_close: bool = True
    close_time: time = time(23, 50)
    
    # Визуализация
    enable_visualization: bool = True
    visualization_port: int = 8050
    visualization_host: str = "127.0.0.1"
    
    # Параметры стратегий
    strategy_config: Optional[dict] = None
    
    # Настройки процесса
    process_name: Optional[str] = None
    log_level: str = "DEBUG"
    
    def __post_init__(self):
        """Инициализация значений по умолчанию после создания"""
        if self.process_name is None:
            self.process_name = f"robot_{self.account_id[:8]}"
        
        if self.strategy_config is None:
            self.strategy_config = {
                'macd_fast': 6,
                'macd_slow': 16,
                'macd_signal': 7,
                'atr_period': 10,
                'lookback_min': 4,
                'lookback_max': 19,
                'peak_prominence': 0.15
            }
    
    def get_process_name(self) -> str:
        """Получить уникальное имя процесса"""
        return f"{self.process_name}_{self.account_id}"
    
    def get_log_file(self) -> str:
        """Получить путь к файлу логов для этого счёта"""
        return f"data/logs/{self.get_process_name()}.log"
    
    def validate(self) -> None:
        """Проверить конфигурацию"""
        if not self.account_id:
            raise ValueError("Обязательно указать account_id")
        if not self.token:
            raise ValueError("Обязательно указать token")
        if not self.figi:
            raise ValueError("Обязательно указать figi")
        if self.deposit <= 0:
            raise ValueError("Депозит должен быть положительным")
        if self.max_daily_loss <= 0:
            raise ValueError("Максимальные дневные потери должны быть положительными")
        if self.visualization_port <= 0 or self.visualization_port > 65535:
            raise ValueError("Порт визуализации должен быть допустимым номером порта")