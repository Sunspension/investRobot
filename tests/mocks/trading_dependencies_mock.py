"""
Мок для всех зависимостей торговой системы
"""
from .api_client_mock import MockAPIClient
from .order_executor_mock import MockOrderExecutor
from .portfolio_manager_mock import MockPortfolioManager
from .risk_manager_mock import MockRiskManager
from .signal_manager_mock import MockSignalManager
from .market_data_stream_mock import MockMarketDataStream

class MockTradingDependencies:
    """Мок для всех зависимостей торговой системы"""
    
    def __init__(self, **kwargs):
        self.api_client = MockAPIClient(**kwargs)
        self.order_executor = MockOrderExecutor(**kwargs)
        self.portfolio_manager = MockPortfolioManager(**kwargs)
        self.risk_manager = MockRiskManager(**kwargs)
        self.signal_manager = MockSignalManager(**kwargs)
        self.market_data_stream = MockMarketDataStream(**kwargs)
