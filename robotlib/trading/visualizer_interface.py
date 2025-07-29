"""
Интерфейс для интеграции визуализатора с торговой системой
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime


class TradingVisualizerable(ABC):
    """Интерфейс для визуализатора торговой системы"""
    
    @abstractmethod
    async def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """
        Добавляет свечу в визуализатор
        
        Args:
            candle_data: Данные свечи (time, open, high, low, close, volume)
        """
        pass
    
    @abstractmethod
    async def add_signal(self, signal_data: Dict[str, Any]) -> None:
        """
        Добавляет торговый сигнал в визуализатор
        
        Args:
            signal_data: Данные сигнала (time, type, price, reason, strategy, etc.)
        """
        pass
    
    @abstractmethod
    async def add_order(self, order_data: Dict[str, Any]) -> None:
        """
        Добавляет ордер в визуализатор
        
        Args:
            order_data: Данные ордера (time, type, price, quantity, strategy, etc.)
        """
        pass
    
    @abstractmethod
    async def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """
        Обновляет информацию о портфеле в визуализаторе
        
        Args:
            portfolio_data: Данные портфеля (balance, positions, pnl, etc.)
        """
        pass
    
    @abstractmethod
    async def update_market_status(self, status_data: Dict[str, Any]) -> None:
        """
        Обновляет статус рынка в визуализаторе
        
        Args:
            status_data: Данные статуса (is_trading, current_time, next_session, etc.)
        """
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Запускает визуализатор"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Останавливает визуализатор"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Проверяет, запущен ли визуализатор"""
        pass


class MockTradingVisualizer(TradingVisualizerable):
    """Мок визуализатора для тестирования"""
    
    def __init__(self):
        self.running = False
        self.candles = []
        self.signals = []
        self.orders = []
        self.portfolio_data = {}
        self.market_status = {}
    
    async def add_candle(self, candle_data: Dict[str, Any]) -> None:
        """Добавляет свечу в мок"""
        self.candles.append(candle_data)
    
    async def add_signal(self, signal_data: Dict[str, Any]) -> None:
        """Добавляет сигнал в мок"""
        self.signals.append(signal_data)
    
    async def add_order(self, order_data: Dict[str, Any]) -> None:
        """Добавляет ордер в мок"""
        self.orders.append(order_data)
    
    async def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """Обновляет портфель в моке"""
        self.portfolio_data.update(portfolio_data)
    
    async def update_market_status(self, status_data: Dict[str, Any]) -> None:
        """Обновляет статус рынка в моке"""
        self.market_status.update(status_data)
    
    async def start(self) -> None:
        """Запускает мок визуализатора"""
        self.running = True
    
    async def stop(self) -> None:
        """Останавливает мок визуализатора"""
        self.running = False
    
    def is_running(self) -> bool:
        """Проверяет, запущен ли мок визуализатора"""
        return self.running
