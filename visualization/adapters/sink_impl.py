from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Any

from robotlib.utils.logger import get_logger
from robotlib.visualization_interfaces import TradingEventSinkable
from visualization.interfaces import DataManagerable
from tinkoff.invest import Candle, HistoricCandle
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderExecution, OrderIntent
from visualization.formatters import to_moscow_time


class VisualizationSinkAdapter(TradingEventSinkable):
    """Адаптер TradingEventSinkable: обновляет DataManager и рассылает WS.

    Выделяет on_candle/on_signal/on_market_status из визуализатора.
    """

    def __init__(self, data_manager: DataManagerable, ws_broadcast: Callable[[Dict[str, Any]], None]) -> None:
        self._data_manager = data_manager
        self._broadcast = ws_broadcast
        self._logger = get_logger(__name__)

    async def on_candle(self, candle: Candle | HistoricCandle, price: float, figi: str) -> None:
        try:
            candle_time = getattr(candle, 'time', datetime.now())
            candle_data = {
                'time': to_moscow_time(candle_time),
                'open': float(getattr(candle.open, 'units', 0) + getattr(candle.open, 'nano', 0) / 1e9),
                'high': float(getattr(candle.high, 'units', 0) + getattr(candle.high, 'nano', 0) / 1e9),
                'low': float(getattr(candle.low, 'units', 0) + getattr(candle.low, 'nano', 0) / 1e9),
                'close': float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9),
                'volume': getattr(candle, 'volume', 0),
            }
            self._data_manager.add_candle(candle_data)
            self._broadcast({"type": "candle", "time": str(candle_data['time']), "price": candle_data['close']})
        except Exception as e:
            self._logger.error(f"Ошибка on_candle: {e}")

    async def on_signal(self, signal: Signal, figi: str, price: float) -> None:
        try:
            signal_data = {
                'time': datetime.now(),
                'type': 'buy' if getattr(signal, 'histogram', 0) > 0 else 'sell',
                'strength': abs(getattr(signal, 'histogram', 0)),
                'macd': getattr(signal, 'macd', 0),
                'signal_line': getattr(signal, 'signal', 0),
                'histogram': getattr(signal, 'histogram', 0),
                'price': price,
            }
            self._data_manager.add_signal(signal_data)
        except Exception as e:
            self._logger.error(f"Ошибка on_signal: {e}")

    async def on_market_status(self, status: dict) -> None:
        try:
            self._data_manager.update_market_status(status)
            self._broadcast({"type": "market_status", "is_trading": status.get('is_trading', False)})
        except Exception as e:
            self._logger.error(f"Ошибка on_market_status: {e}")

    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        """Публикует исполненный ордер в DataManager и пушит короткое WS-сообщение."""
        try:
            ui_order = {
                'order_id': execution.order_id,
                'figi': intent.figi,
                'time': execution.timestamp,
                'type': 'buy' if intent.direction.name.lower() == 'buy' else 'sell',
                'price': execution.price or 0.0,
                'quantity': execution.filled_quantity or intent.quantity,
                'strategy': getattr(intent, 'strategy', None),
                'reason': execution.reason,
            }
            self._data_manager.add_order(ui_order)
            self._broadcast({"type": "order", "side": ui_order['type'], "price": ui_order['price']})
        except Exception as e:
            self._logger.error(f"Ошибка on_order_execution: {e}")
