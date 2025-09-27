"""
Фабрика для создания PositionManager с dependency injection
"""

from typing import Optional
from robotlib.trading.position_manager import PositionManager
from robotlib.trading.position_sync_interface import PositionSyncServiceable
from robotlib.utils.logger import get_logger


class PositionManagerFactory:
    """Фабрика для создания PositionManager"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    @staticmethod
    def create_position_manager(
        db_path: str, 
        risk_manager,
        sync_service: PositionSyncServiceable
    ) -> PositionManager:
        """
        Создает PositionManager с переданными зависимостями
        
        Args:
            db_path: Путь к базе данных
            risk_manager: Менеджер рисков
            sync_service: Сервис синхронизации позиций
            
        Returns:
            PositionManager: Созданный менеджер позиций
        """
        return PositionManager(db_path, risk_manager, sync_service)
    
    @staticmethod
    async def create_and_sync_position_manager(
        db_path: str, 
        risk_manager,
        sync_service: PositionSyncServiceable,
        max_retries: int = 3
    ) -> PositionManager:
        """
        Создает PositionManager и синхронизирует позиции при старте
        
        Args:
            db_path: Путь к базе данных
            risk_manager: Менеджер рисков
            sync_service: Сервис синхронизации позиций
            max_retries: Максимальное количество попыток синхронизации
            
        Returns:
            PositionManager: Созданный и синхронизированный менеджер позиций
        """
        position_manager = PositionManager(db_path, risk_manager, sync_service)
        
        # Синхронизируем позиции при старте
        await position_manager.sync_on_startup(max_retries)
        
        return position_manager
