"""
Мок для всех зависимостей стратегии
"""
from .risk_manager_mock import MockRiskManager
from .portfolio_manager_mock import MockPortfolioManager

class MockStrategyDependencies:
    """Мок для всех зависимостей стратегии"""
    
    def __init__(self, **kwargs):
        self.risk_manager = MockRiskManager(**kwargs)
        self.portfolio_manager = MockPortfolioManager(**kwargs)
