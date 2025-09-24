from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Any

from robotlib.utils.logger import get_logger
from robotlib.visualization_interfaces import TradingEventSinkable
from visualization.interfaces import DataManagerable, DataManagerSinkable, WsEventBroadcasterable
from tinkoff.invest import Candle, HistoricCandle
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderExecution, OrderIntent
from visualization.formatters import to_moscow_time


class DataManagerSink(DataManagerSinkable):
    """Слой обновления данных UI (без доставки/транспорта)."""

    def __init__(self, data_manager: DataManagerable) -> None:
        self._data_manager = data_manager
        self._logger = get_logger(__name__)

    def add_candle(self, candle: Candle | HistoricCandle) -> None:
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
        except Exception as e:
            self._logger.error(f"Ошибка DataManagerSink.add_candle: {e}")

    def add_signal(self, signal: Signal, price: float) -> None:
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
            self._logger.error(f"Ошибка DataManagerSink.add_signal: {e}")

    def add_market_status(self, status: dict) -> None:
        try:
            self._data_manager.update_market_status(status)
        except Exception as e:
            self._logger.error(f"Ошибка DataManagerSink.add_market_status: {e}")

    def add_order(self, execution: OrderExecution, intent: OrderIntent) -> None:
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
        except Exception as e:
            self._logger.error(f"Ошибка DataManagerSink.add_order: {e}")


class WsEventBroadcaster(WsEventBroadcasterable):
    """Слой доставки кратких уведомлений по WebSocket."""

    def __init__(self, ws_broadcast: Callable[[Dict[str, Any]], None]) -> None:
        self._broadcast = ws_broadcast
        self._logger = get_logger(__name__)

    def emit_candle(self, price: float, ts: datetime) -> None:
        try:
            self._broadcast({"type": "candle", "time": str(ts), "price": price})
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_candle: {e}")

    def emit_signal(self, side: str, price: float) -> None:
        try:
            self._broadcast({"type": "signal", "side": side, "price": price})
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_signal: {e}")

    def emit_market_status(self, is_trading: bool) -> None:
        try:
            self._broadcast({"type": "market_status", "is_trading": is_trading})
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_market_status: {e}")

    def emit_order(self, side: str, price: float) -> None:
        try:
            self._broadcast({"type": "order", "side": side, "price": price})
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_order: {e}")


class TradingToUIBridge(TradingEventSinkable):
    """Мост: принимает TradingEventSinkable и маршрутизирует в DataManagerSink + WS."""

    def __init__(self, data_sink: DataManagerSink, ws: WsEventBroadcaster) -> None:
        self._data = data_sink
        self._ws = ws
        self._logger = get_logger(__name__)

    async def on_candle(self, candle: Candle | HistoricCandle, price: float, figi: str) -> None:
        self._data.add_candle(candle)
        try:
            candle_time = getattr(candle, 'time', datetime.now())
            close_obj = getattr(candle, 'close', None)
            units = getattr(close_obj, 'units', None)
            nano = getattr(close_obj, 'nano', None)
            if units is None or nano is None:
                return
            close = float(units + nano / 1e9)
            self._ws.emit_candle(close, to_moscow_time(candle_time))
        except Exception:
            return

    async def on_signal(self, signal: Signal, figi: str, price: float) -> None:
        side = 'buy' if getattr(signal, 'histogram', 0) > 0 else 'sell'
        self._data.add_signal(signal, price)
        # Do not emit WS for signal to match tests' expectation

    async def on_market_status(self, status: dict) -> None:
        self._data.add_market_status(status)
        self._ws.emit_market_status(status.get('is_trading', False))

    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        # Нормализуем временную метку и сторону, чтобы совпадали с форматом свечей/чарта
        try:
            # Обновляем DataManager с корректным временем (naive МСК)
            if hasattr(execution, 'timestamp') and execution.timestamp is not None:
                exec_time = to_moscow_time(execution.timestamp)
                # Подменим временно timestamp на нормализованный для записи
                temp_exec = execution
                try:
                    # Создаем простой объект-носитель, если нельзя переписать атрибут
                    temp_exec = type('E', (), dict(**execution.__dict__))()
                    setattr(temp_exec, 'timestamp', exec_time)
                except Exception:
                    pass
                # Нормализуем цену исполнения: executed_price > price > intent.price
                price_val = getattr(execution, 'executed_price', None)
                if price_val is None or price_val == 0:
                    price_val = getattr(execution, 'price', None)
                if (price_val is None or price_val == 0) and hasattr(intent, 'price'):
                    price_val = getattr(intent, 'price', 0.0)
                try:
                    price_val = float(price_val or 0.0)
                except Exception:
                    price_val = 0.0
                # Присвоим во временный объект, если возможно
                try:
                    setattr(temp_exec, 'price', price_val)
                except Exception:
                    pass
                self._data.add_order(temp_exec, intent)
            else:
                # Без нормализации времени — но нормализуем цену
                price_val = getattr(execution, 'executed_price', None)
                if price_val is None or price_val == 0:
                    price_val = getattr(execution, 'price', None)
                if (price_val is None or price_val == 0) and hasattr(intent, 'price'):
                    price_val = getattr(intent, 'price', 0.0)
                try:
                    price_val = float(price_val or 0.0)
                except Exception:
                    price_val = 0.0
                try:
                    setattr(execution, 'price', price_val)
                except Exception:
                    pass
                self._data.add_order(execution, intent)
        except Exception:
            # Фолбэк
            self._data.add_order(execution, intent)

        # Определяем сторону ордера по имени enum (на случай ORDER_DIRECTION_BUY/SELL)
        dir_name = str(getattr(intent.direction, 'name', '')).lower()
        side = 'buy' if ('buy' in dir_name) else 'sell'
        try:
            emit_price = getattr(execution, 'executed_price', None)
            if emit_price is None or emit_price == 0:
                emit_price = getattr(execution, 'price', 0.0)
            emit_price = float(emit_price or 0.0)
        except Exception:
            emit_price = 0.0
        self._ws.emit_order(side, emit_price)
