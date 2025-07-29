#!/usr/bin/env python3
"""
Фабрика для создания TradingSessionManager
"""
from typing import Any, Dict, Optional
from robotlib.utils.logger import get_logger
from robotlib.trading.trading_config import TradingConfig as TradingSessionConfig
from robotlib.trading.risk_manager import RiskLimits
from robotlib.trading.trading_session import TradingSession
from .trading_dependencies_factory import TradingDependenciesFactory
from ..trading_session_manager import TradingSessionManager
from unittest.mock import Mock


class MockTradingSessionManager:
    """Мок-реализация TradingSessionManager для тестирования"""
    
    def __init__(self, trading_session=None, signal_manager=None, strategy_params=None):
        self.trading_session = trading_session
        self.signal_manager = signal_manager
        self.strategy_params = strategy_params or {}


class TradingSessionManagerFactory:
    """Фабрика для создания TradingSessionManager с правильной инжекцией зависимостей"""
    
    def __init__(self, service_locator=None):
        self.service_locator = service_locator
        self.logger = get_logger(__name__)
    
    def create_real_manager(self, config: Any, strategy_params: Dict[str, Any] = None) -> TradingSessionManager:
        """Создает TradingSessionManager с реальными данными"""
        try:
            # Создаем конфигурацию
            trading_config = TradingSessionConfig(
                figi="FUTIMOEXF000",
                deposit=None,
                signal_manager_params=strategy_params or {},
                risk_limits=RiskLimits(
                    max_daily_loss=50000,
                    max_position_size=50000,
                    percent_from_deposit=50.0,
                    items_per_trade=20,
                    stop_loss_threshold=3.0
                ),
                auto_close_positions=False
            )
            
            # Создаем зависимости
            dependencies_factory = TradingDependenciesFactory()
            try:
                dependencies = dependencies_factory.create_real_dependencies(config)
            except Exception as e:
                self.logger.warning(f"Не удалось создать реальные зависимости: {e}")
                dependencies = dependencies_factory.create_mock_dependencies()
            
            # Создаем TradingSession
            trading_session = TradingSession(
                config=trading_config,
                dependencies=dependencies
            )
            
            return TradingSessionManager(
                trading_session=trading_session,
                strategy_params=strategy_params
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания TradingSessionManager с реальными данными: {e}")
            raise
    
    def create_mock_manager(self, strategy_params: Dict[str, Any] = None) -> TradingSessionManager:
        """Создает TradingSessionManager с мок данными"""
        try:
            # Создаем конфигурацию
            trading_config = TradingSessionConfig(
                figi="FUTIMOEXF000",
                deposit=None,
                signal_manager_params=strategy_params or {},
                risk_limits=RiskLimits(
                    max_daily_loss=50000,
                    max_position_size=50000,
                    percent_from_deposit=50.0,
                    items_per_trade=20,
                    stop_loss_threshold=3.0
                ),
                auto_close_positions=False
            )
            
            # Создаем мок зависимости
            dependencies_factory = TradingDependenciesFactory()
            dependencies = dependencies_factory.create_mock_dependencies()
            
            # Создаем TradingSession
            trading_session = TradingSession(
                config=trading_config,
                dependencies=dependencies
            )
            
            return TradingSessionManager(
                trading_session=trading_session,
                strategy_params=strategy_params
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания TradingSessionManager с мок данными: {e}")
            raise
    
    def create_test_manager(self, strategy_params: Dict[str, Any] = None) -> MockTradingSessionManager:
        """Создает мок TradingSessionManager для тестирования"""
        try:
            # Создаем мок компоненты
            mock_trading_session = Mock()
            mock_signal_manager = Mock()
            
            return MockTradingSessionManager(
                trading_session=mock_trading_session,
                signal_manager=mock_signal_manager,
                strategy_params=strategy_params
            )
        except Exception as e:
            self.logger.error(f"Ошибка создания мок TradingSessionManager: {e}")
            raise
