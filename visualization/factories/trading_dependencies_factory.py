#!/usr/bin/env python3
"""
Фабрика для создания TradingDependencies
"""
from typing import Any
from robotlib.trading.trading_session import TradingConfig
from robotlib.utils.logger import get_logger
from robotlib.trading.interfaces import TradingDependencies
from robotlib.trading.session_stats import SessionStats
from robotlib.trading.session_initializer import SessionInitializer
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.signal_manager import SignalManager
from robotlib.trading.market_data_stream import MarketDataStream
from tests.mocks import MockPortfolioManager, MockRiskManager
from unittest.mock import Mock


class TradingDependenciesFactory:
    """Фабрика для создания TradingDependencies с правильной инжекцией зависимостей"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    def create_real_dependencies(self, config: Any) -> TradingDependencies:
        """Создает зависимости с реальными данными"""
        try:
            # Создаем API клиент
            api_client = TinkoffAPIClient(
                token=config.tcs_client.token,
                account_id=config.tcs_client.id,
                sandbox_token=config.tcs_client.sandbox_token
            )
            
            # Создаем остальные компоненты
            order_executor = OrderExecutor(api_client)
            portfolio_manager = PortfolioManager(api_client)
            
            # Создаем risk_limits по умолчанию
            risk_limits = RiskLimits(
                max_daily_loss=50000,
                max_position_size=50000,
                percent_from_deposit=50.0,
                items_per_trade=20,
                stop_loss_threshold=3.0
            )
            risk_manager = RiskManager(portfolio_manager, risk_limits)
            
            # Создаем signal_manager с параметрами по умолчанию
            signal_manager_params = getattr(config, 'signal_manager_params', {})
            signal_manager = SignalManager(**signal_manager_params)
            # Получаем figi из параметров или используем значение по умолчанию
            figi = getattr(config, 'figi', 'FUTIMOEXF000')
            market_data_stream = MarketDataStream(
                api_client=api_client,
                signal_manager=signal_manager,
                figi=figi,
                visualizer=visualizer
            )
            
            # Создаем компоненты сессии
            session_stats = SessionStats()
            strategy_manager = StrategyManager(
                signal_manager=signal_manager,
                risk_manager=risk_manager,
                portfolio_manager=portfolio_manager,
                order_executor=order_executor
            )
            
            # Создаем базовые зависимости для SessionInitializer
            base_dependencies = TradingDependencies(
                api_client=api_client,
                order_executor=order_executor,
                portfolio_manager=portfolio_manager,
                risk_manager=risk_manager,
                signal_manager=signal_manager,
                strategy_manager=strategy_manager,
                market_data_stream=market_data_stream,
                session_stats=session_stats,
                session_initializer=None  # Временно None, обновим после создания
            )
            
            # Создаем SessionInitializer с базовыми зависимостями
            session_initializer = SessionInitializer(config, base_dependencies)
            
            # Обновляем зависимости с правильным SessionInitializer
            return TradingDependencies(
                api_client=api_client,
                order_executor=order_executor,
                portfolio_manager=portfolio_manager,
                risk_manager=risk_manager,
                signal_manager=signal_manager,
                strategy_manager=strategy_manager,
                market_data_stream=market_data_stream,
                session_stats=session_stats,
                session_initializer=session_initializer
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания реальных зависимостей: {e}")
            raise
    
    def create_mock_dependencies(self) -> TradingDependencies:
        """Создает зависимости с мок данными"""
        try:
            # Создаем мок компоненты
            api_client = Mock()
            order_executor = Mock()
            portfolio_manager = MockPortfolioManager()
            risk_manager = MockRiskManager()
            signal_manager = Mock()
            strategy_manager = Mock()
            market_data_stream = Mock()
            session_stats = Mock()
            session_initializer = Mock()
            
            return TradingDependencies(
                api_client=api_client,
                order_executor=order_executor,
                portfolio_manager=portfolio_manager,
                risk_manager=risk_manager,
                signal_manager=signal_manager,
                strategy_manager=strategy_manager,
                market_data_stream=market_data_stream,
                session_stats=session_stats,
                session_initializer=session_initializer
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания мок зависимостей: {e}")
            raise
