"""
Моки для тестирования стратегий
"""
from unittest.mock import Mock
from typing import Any


class MockRiskManager:
    """Мок для RiskManager с минимальным интерфейсом"""
    
    def __init__(self, **kwargs):
        self.risk_limits = Mock()
        # Устанавливаем значения по умолчанию
        self.risk_limits.percent_from_deposit = kwargs.get('percent_from_deposit', 50.0)
        self.risk_limits.items_per_trade = kwargs.get('items_per_trade', 20)
        self.risk_limits.stop_loss_threshold = kwargs.get('stop_loss_threshold', 8.0)


class MockPortfolioManager:
    """Мок для PortfolioManager с минимальным интерфейсом"""
    
    def __init__(self, **kwargs):
        self._deposit = kwargs.get('deposit', 100000.0)
        self._guarantee_deposit = kwargs.get('guarantee_deposit', 1700.0)
        self._point_value = kwargs.get('point_value', 10.0)
        self._contracts_per_lot = kwargs.get('contracts_per_lot', 10)
    
    async def get_deposit(self) -> float:
        """Возвращает мок депозита"""
        return self._deposit
    
    async def get_guarantee_deposit(self, figi: str) -> float:
        """Возвращает мок гарантийного обеспечения"""
        return self._guarantee_deposit
    
    async def get_point_value(self, figi: str) -> float:
        """Возвращает мок стоимости одного пункта"""
        return self._point_value
    
    async def get_contracts_per_lot(self, figi: str) -> int:
        """Возвращает мок количества контрактов в лоте"""
        return self._contracts_per_lot


class MockStrategyDependencies:
    """Мок для всех зависимостей стратегии"""
    
    def __init__(self, **kwargs):
        self.risk_manager = MockRiskManager(**kwargs)
        self.portfolio_manager = MockPortfolioManager(**kwargs)
