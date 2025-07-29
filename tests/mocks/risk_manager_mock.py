"""
Мок для RiskManager с минимальным интерфейсом
"""
from unittest.mock import Mock

class MockRiskManager:
    """Мок для RiskManager с минимальным интерфейсом"""
    
    def __init__(self, **kwargs):
        self.risk_limits = Mock()
        # Устанавливаем значения по умолчанию
        self.risk_limits.percent_from_deposit = kwargs.get('percent_from_deposit', 50.0)
        self.risk_limits.items_per_trade = kwargs.get('items_per_trade', 20)
        self.risk_limits.stop_loss_threshold = kwargs.get('stop_loss_threshold', 8.0)
