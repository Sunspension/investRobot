"""
Моки для тестирования компонентов торговой сессии
"""
from datetime import datetime
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock

from robotlib.trading.session_interfaces import (
    SessionStatsable, 
    SessionInitializable, 
    SessionControllable, 
    TradingSessionable
)


class MockSessionStats(SessionStatsable):
    """Мок для SessionStats"""
    
    def __init__(self):
        self._start_time = datetime.now()
        self._end_time = None
        self._total_signals = 0
        self._successful_orders = 0
        self._failed_orders = 0
        self._total_volume = 0.0
        self._total_profit = 0.0
        self._max_drawdown = 0.0
        self._current_drawdown = 0.0
        self._peak_balance = 0.0
        self._current_balance = 0.0
    
    def add_signal(self) -> None:
        self._total_signals += 1
    
    def add_successful_order(self, volume: float, profit: float = 0.0) -> None:
        self._successful_orders += 1
        self._total_volume += volume
        self._total_profit += profit
    
    def add_failed_order(self) -> None:
        self._failed_orders += 1
    
    def update_balance(self, new_balance: float) -> None:
        self._current_balance = new_balance
        if new_balance > self._peak_balance:
            self._peak_balance = new_balance
            self._current_drawdown = 0.0
        else:
            self._current_drawdown = self._peak_balance - new_balance
            if self._current_drawdown > self._max_drawdown:
                self._max_drawdown = self._current_drawdown
    
    def get_stats_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self._start_time.isoformat(),
            'end_time': self._end_time.isoformat() if self._end_time else None,
            'total_signals': self._total_signals,
            'successful_orders': self._successful_orders,
            'failed_orders': self._failed_orders,
            'success_rate': self._successful_orders / max(1, self._successful_orders + self._failed_orders),
            'total_volume': self._total_volume,
            'total_profit': self._total_profit,
            'max_drawdown': self._max_drawdown,
            'current_drawdown': self._current_drawdown,
            'peak_balance': self._peak_balance,
            'current_balance': self._current_balance
        }
    
    def print_stats(self) -> None:
        pass  # Мок не выводит в консоль
    
    def finish_session(self) -> None:
        self._end_time = datetime.now()
    
    @property
    def start_time(self) -> datetime:
        return self._start_time
    
    @property
    def end_time(self) -> Optional[datetime]:
        return self._end_time
    
    @property
    def total_signals(self) -> int:
        return self._total_signals
    
    @property
    def successful_orders(self) -> int:
        return self._successful_orders
    
    @property
    def failed_orders(self) -> int:
        return self._failed_orders
    
    @property
    def total_volume(self) -> float:
        return self._total_volume
    
    @property
    def total_profit(self) -> float:
        return self._total_profit
    
    @property
    def current_balance(self) -> float:
        return self._current_balance


class MockSessionInitializer(SessionInitializable):
    """Мок для SessionInitializer"""
    
    def __init__(self):
        self.initialize_components_called = False
        self.initialize_strategies_called = False
        self.initialize_data_streams_called = False
        self.check_risk_limits_called = False
    
    async def initialize_components(self) -> None:
        self.initialize_components_called = True
    
    async def initialize_strategies(self) -> None:
        self.initialize_strategies_called = True
    
    async def initialize_data_streams(self) -> None:
        self.initialize_data_streams_called = True
    
    async def check_risk_limits(self) -> None:
        self.check_risk_limits_called = True


class MockSessionController(SessionControllable):
    """Мок для SessionController"""
    
    def __init__(self):
        self._is_running = False
        self._is_initialized = False
        self._stats = MockSessionStats()
        self.start_called = False
        self.stop_called = False
        self.run_trading_loop_called = False
    
    async def start(self) -> bool:
        self.start_called = True
        self._is_running = True
        self._is_initialized = True
        return True
    
    async def stop(self) -> None:
        self.stop_called = True
        self._is_running = False
    
    async def run_trading_loop(self) -> None:
        self.run_trading_loop_called = True
    
    async def get_session_status(self) -> Dict[str, Any]:
        return {
            'is_running': self._is_running,
            'is_initialized': self._is_initialized,
            'stats': self._stats.get_stats_dict()
        }
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def is_initialized(self) -> bool:
        return self._is_initialized
    
    @property
    def stats(self) -> SessionStatsable:
        return self._stats


class MockTradingSession(TradingSessionable):
    """Мок для TradingSession"""
    
    def __init__(self):
        self._controller = MockSessionController()
        self.start_called = False
        self.stop_called = False
        self.run_trading_loop_called = False
        self.execute_signal_called = False
        self.close_all_positions_called = False
    
    async def start(self) -> bool:
        self.start_called = True
        return await self._controller.start()
    
    async def stop(self) -> None:
        self.stop_called = True
        await self._controller.stop()
    
    async def run_trading_loop(self) -> None:
        self.run_trading_loop_called = True
        await self._controller.run_trading_loop()
    
    def get_stats(self) -> Dict[str, Any]:
        return self._controller.stats.get_stats_dict()
    
    def print_stats(self) -> None:
        self._controller.stats.print_stats()
    
    async def execute_signal(self, signal) -> None:
        self.execute_signal_called = True
    
    async def get_session_status(self) -> Dict[str, Any]:
        return await self._controller.get_session_status()
    
    async def close_all_positions(self) -> None:
        self.close_all_positions_called = True
