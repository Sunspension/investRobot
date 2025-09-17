from __future__ import annotations

from datetime import datetime
from typing import Any

from robotlib.utils.logger import get_logger
from robotlib.visualization_interfaces import TradingEventSinkable
from visualization.formatters import to_moscow_time


class VisualizationSinkAdapter(TradingEventSinkable):
    """Адаптер TradingEventSinkable: обновляет DataManager и рассылает WS.

    Выделяет on_candle/on_signal/on_market_status из визуализатора.
    """

    def __init__(self, data_manager, ws_broadcast) -> None:
        self._data_manager = data_manager
        self._broadcast = ws_broadcast
        self._logger = get_logger(__name__)

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
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

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
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
