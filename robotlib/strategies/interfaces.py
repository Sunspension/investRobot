"""
Интерфейсы для стратегий - обеспечивают инверсию зависимостей
"""
from abc import ABC, abstractmethod
from typing import Protocol


class RiskManageable(Protocol):
    """Интерфейс для риск-менеджера"""
    
    @property
    def risk_limits(self):
        """Возвращает лимиты рисков"""
        pass


class PortfolioManageable(Protocol):
    """Интерфейс для портфель-менеджера"""
    
    async def get_deposit(self) -> float:
        """Получить текущий депозит"""
        pass
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        """Получить гарантийное обеспечение для инструмента"""
        pass
    
    async def get_point_value(self, figi: str) -> float:
        """Получить стоимость одного пункта для инструмента"""
        pass
    
    async def get_contracts_per_lot(self, figi: str) -> int:
        """Получить количество контрактов в одном лоте для инструмента"""
        pass


class PositionSizingManageable(Protocol):
    """Интерфейс для сервиса расчета размера позиции"""
    
    async def calculate_position_size(
        self,
        signal,
        current_position: int,
        figi: str = "FUTIMOEXF000"
    ) -> int:
        """Рассчитать рекомендуемый размер позиции"""
        pass


class StrategyDependencies:
    """Контейнер для зависимостей стратегии"""
    
    def __init__(
        self, 
        risk_manager: RiskManageable, 
        portfolio_manager: PortfolioManageable,
        position_sizing_service: PositionSizingManageable
    ):
        self.risk_manager = risk_manager
        self.portfolio_manager = portfolio_manager
        self.position_sizing_service = position_sizing_service
