"""
Типовые интерфейсы (Protocols) для визуализатора и его зависимостей.
"""
from __future__ import annotations

from typing import Protocol, List, Dict, Any, runtime_checkable
from plotly.graph_objects import Figure


@runtime_checkable
class StrategyDataProvider(Protocol):
    def get_strategy_status(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class TradingSessionDataProvider(Protocol):
    def __init__(self, session_controller) -> None:  # noqa: ANN401 (decoupling)
        ...

    def get_strategy_status(self) -> List[Dict[str, Any]]:
        ...


@runtime_checkable
class DataManagerable(Protocol):
    def get_data_snapshot(self) -> Dict[str, Any]:
        ...

    def add_candle(self, candle_data: Dict[str, Any]) -> None:
        ...

    def add_signal(self, signal_data: Dict[str, Any]) -> None:
        ...

    def add_order(self, order_data: Dict[str, Any]) -> None:
        ...

    def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        ...

    def update_strategies_data(self, strategies_data: List[Dict[str, Any]]) -> None:
        ...


@runtime_checkable
class ChartBuilderable(Protocol):
    def create_trading_chart(
        self,
        candles_data: List[Dict[str, Any]],
        orders_data: List[Dict[str, Any]],
        current_price: float = 0.0,
        hide_inactive_time: bool = True,
    ) -> Figure:
        ...


@runtime_checkable
class UIComponentsable(Protocol):
    def _get_custom_html_template(self) -> str:
        ...

    def _create_layout(self):  # Dash layout (typed at runtime)
        ...


@runtime_checkable
class DataManagerSinkable(Protocol):
    def add_candle(self, candle) -> None:  # Candle | HistoricCandle at runtime
        ...

    def add_signal(self, signal, price: float) -> None:  # Signal at runtime
        ...

    def add_market_status(self, status: Dict[str, Any]) -> None:
        ...

    def add_order(self, execution, intent) -> None:  # OrderExecution, OrderIntent at runtime
        ...


@runtime_checkable
class WsEventBroadcasterable(Protocol):
    def emit_candle(self, price: float, ts) -> None:
        ...

    def emit_signal(self, side: str, price: float) -> None:
        ...

    def emit_market_status(self, is_trading: bool) -> None:
        ...

    def emit_order(self, side: str, price: float) -> None:
        ...


