#!/usr/bin/env python3
"""
Интерфейсы для системы визуализации
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


# TradingConfig перенесен в robotlib.trading.trading_session


class DependenciesProvidable(ABC):
    """Интерфейс провайдера зависимостей для визуализации"""
    
    @abstractmethod
    def get_trading_session_factory(self) -> Any:
        """Возвращает фабрику TradingSession"""
        pass
    
    @abstractmethod
    def get_strategy_manager_factory(self) -> Any:
        """Возвращает фабрику StrategyManager"""
        pass


# Алиас для обратной совместимости
DependenciesProvider = DependenciesProvidable


class DependenciesProviderFactoryable(ABC):
    """Интерфейс фабрики провайдеров зависимостей"""
    
    @abstractmethod
    def create_real_data_provider(self, config: Any) -> DependenciesProvidable:
        """Создает провайдер для реальных данных"""
        pass
    
    @abstractmethod
    def create_mock_data_provider(self) -> DependenciesProvidable:
        """Создает провайдер для мок данных"""
        pass
    


