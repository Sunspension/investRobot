"""
Интерфейс для сервиса восстановления позиций
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class FIFOEntry:
    """Запись FIFO очереди"""
    quantity: int
    price: float
    timestamp: datetime
    order_id: str
    direction: str


@dataclass
class Position:
    """Позиция по инструменту"""
    figi: str
    quantity: int
    avg_price: float
    last_updated: datetime


class PositionRestorationServiceable(ABC):
    """
    Интерфейс для сервиса восстановления позиций
    """
    
    @abstractmethod
    async def restore_fifo_from_api(
        self, 
        api_positions: Dict[str, Position],
        existing_fifo: Dict[str, List[FIFOEntry]],
        days_back: int = 30
    ) -> Dict[str, List[FIFOEntry]]:
        """
        Восстанавливает FIFO данные из API истории операций
        
        Args:
            api_positions: Позиции из API
            existing_fifo: Существующие FIFO данные
            days_back: Количество дней назад для поиска операций
            
        Returns:
            Словарь с восстановленными FIFO данными по FIGI
        """
        pass
    
    @abstractmethod
    async def validate_restored_fifo(
        self, 
        fifo_data: Dict[str, List[FIFOEntry]]
    ) -> Dict[str, bool]:
        """
        Валидирует восстановленные FIFO данные
        
        Args:
            fifo_data: FIFO данные для валидации
            
        Returns:
            Словарь с результатами валидации по FIGI
        """
        pass
