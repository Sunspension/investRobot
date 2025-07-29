#!/usr/bin/env python3
"""
Провайдер зависимостей для системы визуализации
"""
import warnings
from typing import Any, Optional
from .interfaces import DependenciesProvidable
from robotlib.trading.trading_session import TradingConfig
from robotlib.utils.logger import get_logger
from robotlib.trading.risk_manager import RiskLimits


class VisualizationDependenciesProvider(DependenciesProvidable):
    """Провайдер зависимостей для визуализации"""
    
    def __init__(self, config: Any = None, use_real_data: bool = True):
        self.config = config
        self.use_real_data = use_real_data
        self.logger = get_logger("dependencies_provider")
        
        # Кэшированные фабрики (deprecated)
        self._trading_session_factory: Optional[Any] = None
        self._strategy_manager_factory: Optional[Any] = None
    
    def get_trading_session_factory(self) -> Any:
        """Возвращает фабрику TradingSession (deprecated)"""
        self.logger.warning("get_trading_session_factory deprecated, используйте TradingDependenciesFactory")
        return None
    
    def get_strategy_manager_factory(self) -> Any:
        """Возвращает фабрику StrategyManager (deprecated)"""
        self.logger.warning("get_strategy_manager_factory deprecated, используйте TradingDependenciesFactory")
        return None


    
