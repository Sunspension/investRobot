from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Callable, Dict, Any
from datetime import timezone as _tz

from robotlib.utils.logger import get_logger
from robotlib.trading_interfaces import TradingEventSinkable
from visualization.interfaces import VisualizationDataStoreable, TradingDataMapperable, WsEventBroadcasterable
from tinkoff.invest import Candle, HistoricCandle
from robotlib.signal_types import Signal
from robotlib.trading.order_types import OrderExecution, OrderIntent
from visualization.formatters import to_moscow_time


class TradingDataMapper(TradingDataMapperable):
    """Маппер торговых данных для визуализации."""

    def __init__(self, data_manager: VisualizationDataStoreable) -> None:
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
            self._logger.error(f"Ошибка TradingDataMapper.add_candle: {e}")
            raise  # Перебрасываем исключение для обработки в TradingToUIBridge

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
            self._logger.error(f"Ошибка TradingDataMapper.add_signal: {e}")

    def add_market_status(self, status: dict) -> None:
        try:
            self._data_manager.update_market_status(status)
        except Exception as e:
            self._logger.error(f"Ошибка TradingDataMapper.add_market_status: {e}")

    def add_order(self, execution: OrderExecution, intent: OrderIntent) -> None:
        try:
            order_data = {
                'time': to_moscow_time(execution.timestamp),
                # Единое поле стороны для UI/БД
                'direction': 'buy' if getattr(intent, 'direction', None) and str(getattr(intent, 'direction').value).lower() == 'buy' else 'sell',
                'price': float(getattr(execution, 'executed_price', 0) or getattr(execution, 'price', 0)),
                'quantity': getattr(intent, 'quantity', 0),
                'strategy': getattr(intent, 'strategy', None),
                'reason': getattr(execution, 'reason', None),
                'status': getattr(execution, 'status', 'unknown'),
                'order_id': getattr(execution, 'order_id', None),
                'figi': getattr(intent, 'figi', 'unknown'),
            }
            self._data_manager.add_order(order_data)
        except Exception as e:
            self._logger.error(f"Ошибка TradingDataMapper.add_order: {e}")

    def get_data_snapshot(self) -> Dict[str, Any]:
        """Получает полный снэпшот данных из VisualizationDataStore"""
        return self._data_manager.get_data_snapshot()


class WsEventBroadcaster(WsEventBroadcasterable):
    """Слой доставки событий через WebSocket."""

    def __init__(self, broadcast_func: Callable[[Dict[str, Any]], None]) -> None:
        self._broadcast = broadcast_func
        self._logger = get_logger(__name__)
        self._seq: int = 0

    def _envelope(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Добавляет метаданные в WS-сообщение."""
        try:
            now_utc = datetime.now(_tz.utc).isoformat().replace('+00:00', 'Z')
        except Exception:
            now_utc = None
        # Монотонная последовательность для идемпотентности на клиенте
        try:
            self._seq += 1
            seq = self._seq
        except Exception:
            seq = None
        meta = {
            'version': 1,
            'server_time_utc': now_utc,
            'seq': seq,
        }
        meta.update(payload)
        return meta

    def emit_snapshot(self, snapshot: dict) -> None:
        try:
            self._broadcast(self._envelope({
                'type': 'snapshot',
                'data': snapshot
            }))
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_snapshot: {e}")

    def emit_init_snapshot(self, snapshot: dict) -> None:
        try:
            self._broadcast(self._envelope({
                'type': 'init_snapshot',
                'data': snapshot
            }))
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_init_snapshot: {e}")

    def emit_candle_update(self, candle_update: dict) -> None:
        try:
            self._broadcast(self._envelope(candle_update))
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_candle_update: {e}")

    def emit_signal_update(self, signal_update: dict) -> None:
        try:
            self._broadcast(self._envelope(signal_update))
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_signal_update: {e}")

    def emit_delta_batch(self, *, candles: list | None, signals: list | None) -> None:
        try:
            payload: Dict[str, Any] = {
                'type': 'delta_batch',
                'candles': candles or [],
                'signals': signals or [],
            }
            self._broadcast(self._envelope(payload))
        except Exception as e:
            self._logger.error(f"Ошибка WsEventBroadcaster.emit_delta_batch: {e}")


class TradingToUIBridge(TradingEventSinkable):
    """
    Мост между торговой системой и UI.
    Получает события от торговой системы и отправляет их в UI через WebSocket.
    """

    def __init__(self, data_mapper: TradingDataMapperable, ws: WsEventBroadcasterable) -> None:
        self._data = data_mapper
        self._ws = ws
        self._logger = get_logger(__name__)
        self._snapshot_task = None
        self._snapshot_interval = 60  # 60 секунд
        # Batching инкрементов
        self._batch_enabled: bool = True
        self._batch_interval_sec: float = 0.2
        self._max_buffer_size: int = 500
        self._candles_buffer: list = []
        self._signals_buffer: list = []
        self._flush_task: asyncio.Task | None = None

    def _schedule_flush(self) -> None:
        if not self._batch_enabled:
            return
        if self._flush_task is None or self._flush_task.done():
            try:
                self._flush_task = asyncio.create_task(self._flush_loop())
            except Exception:
                self._flush_task = None

    async def _flush_loop(self) -> None:
        try:
            await asyncio.sleep(self._batch_interval_sec)
            if self._candles_buffer or self._signals_buffer:
                candles = self._candles_buffer[:]
                signals = self._signals_buffer[:]
                self._candles_buffer.clear()
                self._signals_buffer.clear()
                self._ws.emit_delta_batch(candles=candles, signals=signals)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Ошибка flush_loop: {e}")
        finally:
            self._flush_task = None

    async def on_candle(self, candle: Candle | HistoricCandle, price: float, figi: str) -> None:
        try:
            self._data.add_candle(candle)
            # Инкрементальное обновление для свечей
            candle_data = {
                'time': to_moscow_time(getattr(candle, 'time', datetime.now())),
                'open': float(getattr(candle.open, 'units', 0) + getattr(candle.open, 'nano', 0) / 1e9),
                'high': float(getattr(candle.high, 'units', 0) + getattr(candle.high, 'nano', 0) / 1e9),
                'low': float(getattr(candle.low, 'units', 0) + getattr(candle.low, 'nano', 0) / 1e9),
                'close': float(getattr(candle.close, 'units', 0) + getattr(candle.close, 'nano', 0) / 1e9),
                'volume': getattr(candle, 'volume', 0),
            }
            if self._batch_enabled:
                self._candles_buffer.append(candle_data)
                if (len(self._candles_buffer) + len(self._signals_buffer)) > self._max_buffer_size:
                    # При перегрузе шлем полный снапшот
                    self._ws.emit_snapshot(self._data.get_data_snapshot())
                    self._candles_buffer.clear()
                    self._signals_buffer.clear()
                else:
                    self._schedule_flush()
            else:
                self._ws.emit_candle_update({
                    'type': 'candle_added',
                    'candle': candle_data
                })
        except Exception as e:
            self._logger.error(f"Ошибка TradingToUIBridge.on_candle: {e}")
            # При ошибке не отправляем обновление

    async def on_signal(self, signal: Signal, figi: str, price: float) -> None:
        try:
            self._data.add_signal(signal, price)
            # Инкрементальное обновление для сигналов
            signal_data = {
                'time': datetime.now(),
                'type': 'buy' if getattr(signal, 'histogram', 0) > 0 else 'sell',
                'strength': abs(getattr(signal, 'histogram', 0)),
                'macd': getattr(signal, 'macd', 0),
                'signal_line': getattr(signal, 'signal', 0),
                'histogram': getattr(signal, 'histogram', 0),
                'price': price,
            }
            if self._batch_enabled:
                self._signals_buffer.append(signal_data)
                if (len(self._candles_buffer) + len(self._signals_buffer)) > self._max_buffer_size:
                    self._ws.emit_snapshot(self._data.get_data_snapshot())
                    self._candles_buffer.clear()
                    self._signals_buffer.clear()
                else:
                    self._schedule_flush()
            else:
                self._ws.emit_signal_update({
                    'type': 'signal_added',
                    'signal': signal_data
                })
        except Exception as e:
            self._logger.error(f"Ошибка TradingToUIBridge.on_signal: {e}")
            # При ошибке не отправляем обновление

    async def on_market_status(self, status: dict) -> None:
        try:
            self._data.add_market_status(status)
            # Отправляем полный снэпшот через WebSocket
            self._ws.emit_snapshot(self._data.get_data_snapshot())
        except Exception as e:
            self._logger.error(f"Ошибка TradingToUIBridge.on_market_status: {e}")

    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        # Нормализуем временную метку и сторону, чтобы совпадали с форматом свечей/чарта
        try:
            # Обновляем VisualizationDataStore с корректным временем (naive МСК)
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
                self._data.add_order(temp_exec, intent)
            else:
                self._data.add_order(execution, intent)
        except Exception as e:
            self._logger.error(f"Ошибка TradingToUIBridge.on_order_execution: {e}")

        # Отправляем полный снэпшот через WebSocket
        self._ws.emit_snapshot(self._data.get_data_snapshot())

    async def start_periodic_snapshots(self) -> None:
        """Запускает периодические снэпшоты для синхронизации"""
        if self._snapshot_task is None:
            # Отправляем начальный снэпшот сразу при запуске
            snapshot = self._data.get_data_snapshot()
            self._ws.emit_snapshot(snapshot)
            self._logger.info("Отправлен начальный снэпшот данных")
            
            self._snapshot_task = asyncio.create_task(self._periodic_snapshot_loop())
            self._logger.info(f"Запущены периодические снэпшоты каждые {self._snapshot_interval} секунд")

    async def stop_periodic_snapshots(self) -> None:
        """Останавливает периодические снэпшоты"""
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
            self._snapshot_task = None
            self._logger.info("Периодические снэпшоты остановлены")
    
    def send_snapshot_on_demand(self) -> None:
        """Отправляет снэпшот по требованию (например, при подключении нового WebSocket клиента)"""
        try:
            snapshot = self._data.get_data_snapshot()
            # Для первых подключений отправляем init_snapshot
            self._ws.emit_init_snapshot(snapshot)
            self._logger.info("Отправлен init_snapshot по требованию")
        except Exception as e:
            self._logger.error(f"Ошибка отправки снэпшота по требованию: {e}")

    async def _periodic_snapshot_loop(self) -> None:
        """Цикл периодических снэпшотов"""
        while True:
            try:
                await asyncio.sleep(self._snapshot_interval)
                self._ws.emit_snapshot(self._data.get_data_snapshot())
                self._logger.debug("Отправлен периодический снэпшот")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Ошибка периодического снэпшота: {e}")