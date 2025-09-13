#!/usr/bin/env python3
"""
Интерфейсы для визуализации
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from robotlib.trading.session_interfaces import TradingSessionable


class StrategyDataProvider(ABC):
    """Интерфейс для получения данных о стратегиях"""
    
    @abstractmethod
    def get_strategy_status(self) -> List[Dict[str, Any]]:
        """Возвращает статус стратегий"""
        pass
    
    @abstractmethod
    def get_strategies_count(self) -> int:
        """Возвращает количество стратегий"""
        pass
    
    @abstractmethod
    def has_strategies(self) -> bool:
        """Проверяет, есть ли стратегии"""
        pass


class TradingSessionDataProvider(StrategyDataProvider):
    """Провайдер данных из TradingSession"""
    
    def __init__(self, trading_session: TradingSessionable):
        self.trading_session = trading_session
    
    def get_strategy_status(self) -> List[Dict[str, Any]]:
        """Получает статус стратегий из TradingSession"""
        try:
            if not self.trading_session or not self.trading_session.dependencies:
                return []
            
            strategy_manager = self.trading_session.dependencies.strategy_manager
            if not strategy_manager or not strategy_manager.has_strategies():
                return []
            
            strategy_status = []
            for strategy in strategy_manager.get_strategies():
                strategy_name = strategy.__class__.__name__
                
                # Получаем информацию о стратегии
                income = getattr(strategy, 'income', 0)
                position = getattr(strategy, 'position', 0)
                
                strategy_status.append({
                    'name': strategy_name,
                    'income': income,
                    'position': position,
                    'status': 'active' if position != 0 else 'waiting'
                })
            
            return strategy_status
            
        except Exception as e:
            # Логируем ошибку, но не прерываем работу
            return []
    
    def get_strategies_count(self) -> int:
        """Возвращает количество стратегий"""
        try:
            if (self.trading_session and 
                self.trading_session.dependencies and 
                self.trading_session.dependencies.strategy_manager):
                return self.trading_session.dependencies.strategy_manager.get_strategies_count()
            return 0
        except Exception:
            return 0
    
    def has_strategies(self) -> bool:
        """Проверяет, есть ли стратегии"""
        try:
            if (self.trading_session and 
                self.trading_session.dependencies and 
                self.trading_session.dependencies.strategy_manager):
                return self.trading_session.dependencies.strategy_manager.has_strategies()
            return False
        except Exception:
            return False


class MockStrategyDataProvider(StrategyDataProvider):
    """Мок-провайдер для тестирования"""
    
    def __init__(self):
        self.mock_strategies = [
            {'name': 'LongStrategy', 'income': 100.0, 'position': 1, 'status': 'active'},
            {'name': 'ShortStrategy', 'income': -50.0, 'position': -1, 'status': 'active'}
        ]
    
    def get_strategy_status(self) -> List[Dict[str, Any]]:
        """Возвращает мок данные о стратегиях"""
        return self.mock_strategies.copy()
    
    def get_strategies_count(self) -> int:
        """Возвращает количество мок стратегий"""
        return len(self.mock_strategies)
    
    def has_strategies(self) -> bool:
        """Всегда возвращает True для мок данных"""
        return True


# Интерфейсы для компонентов визуализации
class DataManagerable(ABC):
    """Интерфейс для менеджера данных"""
    
    @abstractmethod
    def update_strategies_data(self, strategies_data: List[Dict[str, Any]]) -> None:
        """Обновляет данные о стратегиях"""
        pass


class ChartBuilderable(ABC):
    """Интерфейс для построителя графиков"""
    
    @abstractmethod
    def create_chart(self, data: Dict[str, Any]) -> Any:
        """Создает график"""
        pass


class UIComponentsable(ABC):
    """Интерфейс для UI компонентов"""
    
    @abstractmethod
    def create_layout(self) -> Any:
        """Создает макет интерфейса"""
        pass
