"""
Централизованная папка для всех моков
Каждый мок в отдельном файле для удобства навигации и поддержки
"""

# API клиенты
from .api_client_mock import MockAPIClient
from .tinkoff_api_client_mock import MockTinkoffAPIClient

# Менеджеры
from .portfolio_manager_mock import MockPortfolioManager
from .risk_manager_mock import MockRiskManager
from .signal_manager_mock import MockSignalManager

# Исполнители
from .order_executor_mock import MockOrderExecutor

# Потоки данных
from .market_data_stream_mock import MockMarketDataStream

# Сессии (уже существующие)
from .session_mocks import (
    MockSessionStats, 
    MockSessionInitializer, 
    MockSessionController, 
    MockTradingSession
)

# Зависимости
from .strategy_dependencies_mock import MockStrategyDependencies
from .trading_dependencies_mock import MockTradingDependencies

# Экспорт всех моков для удобного импорта
__all__ = [
    # API клиенты
    'MockAPIClient',
    'MockTinkoffAPIClient',
    
    # Менеджеры
    'MockPortfolioManager',
    'MockRiskManager', 
    'MockSignalManager',
    
    # Исполнители
    'MockOrderExecutor',
    
    # Потоки данных
    'MockMarketDataStream',
    
    # Сессии
    'MockSessionStats',
    'MockSessionInitializer',
    'MockSessionController',
    'MockTradingSession',
    
    # Зависимости
    'MockStrategyDependencies',
    'MockTradingDependencies',
]
