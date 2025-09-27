"""
Конфигурация торговой сессии
"""
from datetime import time


class TradingConfig:
    """Конфигурация торговой сессии"""
    def __init__(
        self, 
        figi: str, 
        auto_close_positions: bool = True,
        end_of_day_close: bool = True,
        close_time: time = time(23, 50),  # Время закрытия позиций
        warning_periods: list[int] = [600, 300, 60],  # Периоды предупреждений в секундах
        enable_visualization: bool = False,  # Включить визуализацию
        positions_db_path: str = "data/positions.db",  # Путь к базе данных для позиций
        market_db_path: str = "data/market.db",  # Путь к базе данных для ордеров и свечей
    ):
        self.figi = figi
        self.auto_close_positions = auto_close_positions
        self.end_of_day_close = end_of_day_close
        self.close_time = close_time
        self.warning_periods = sorted(warning_periods, reverse=True)  # Сортируем по убыванию
        self.enable_visualization = enable_visualization
        self.positions_db_path = positions_db_path
        self.market_db_path = market_db_path
