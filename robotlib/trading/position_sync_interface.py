"""
Интерфейс для сервиса синхронизации позиций
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FIFOEntry:
    """Запись в FIFO очереди"""
    quantity: int
    price: float
    timestamp: datetime
    order_id: str
    direction: str  # 'buy' или 'sell'


@dataclass
class Position:
    """Информация о позиции"""
    figi: str
    quantity: int
    avg_price: float
    last_updated: datetime


class PositionSyncServiceable(ABC):
    """
    Интерфейс для сервиса синхронизации и восстановления позиций
    """
    
    @abstractmethod
    async def sync_positions_on_startup(self, max_retries: int = 3) -> Dict[str, Position]:
        """
        Полная синхронизация позиций при старте с восстановлением FIFO
        
        Args:
            max_retries: Максимальное количество попыток
            
        Returns:
            Словарь позиций {figi: Position}
        """
        pass
    
    @abstractmethod
    async def get_fifo_cache(self) -> Dict[str, List[FIFOEntry]]:
        """
        Получает FIFO кэш из БД
        
        Returns:
            Словарь FIFO данных {figi: List[FIFOEntry]}
        """
        pass
    
    @abstractmethod
    async def save_fifo_cache(self, fifo_cache: Dict[str, List[FIFOEntry]]):
        """
        Сохраняет FIFO кэш в БД
        
        Args:
            fifo_cache: FIFO данные для сохранения
        """
        pass
