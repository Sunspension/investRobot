from __future__ import annotations

import asyncio
from typing import Any, Optional

from tinkoff.invest import Candle, HistoricCandle

from robotlib.utils.logger import get_logger
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import DBCandle, upsert_candles
from visualization.event_visualizer_interface import VisualizationSinkable


class DBIngestionSink(VisualizationSinkable):
    """Visualization sink that persists candles into SQLite in the background.

    Designed to be injected into `MarketDataStream` so that both historical
    warm-up candles and live stream candles are stored independently of the
    trading system/strategies.
    """

    def __init__(
        self,
        *,
        db_path: str,
        figi: str,
        batch_size: int = 500,
        flush_interval_sec: float = 1.0,
    ) -> None:
        self._logger = get_logger(__name__)
        self._db_path = db_path
        self._figi = figi
        self._batch_size = max(1, batch_size)
        self._flush_interval_sec = max(0.1, flush_interval_sec)

        self._queue: asyncio.Queue[DBCandle] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._closed: bool = False
        self._started: bool = False

    async def _ensure_started(self) -> None:
        if self._started:
            return
        # Initialize DB schema and start background worker once
        await init_db(self._db_path)
        self._worker_task = asyncio.create_task(self._worker(), name="db_ingestion_sink_worker")
        self._started = True
        self._logger.info(
            f"DBIngestionSink started: db_path={self._db_path}, figi={self._figi}, "
            f"batch_size={self._batch_size}, flush_interval_sec={self._flush_interval_sec}"
        )

    async def _worker(self) -> None:
        buffer: list[DBCandle] = []
        try:
            while not self._closed or not self._queue.empty() or buffer:
                try:
                    item: DBCandle = await asyncio.wait_for(
                        self._queue.get(), timeout=self._flush_interval_sec
                    )
                    buffer.append(item)
                    if len(buffer) >= self._batch_size:
                        await upsert_candles(self._db_path, buffer)
                        self._logger.debug(f"Flushed {len(buffer)} candles to DB")
                        buffer.clear()
                except asyncio.TimeoutError:
                    if buffer:
                        await upsert_candles(self._db_path, buffer)
                        self._logger.debug(f"Flushed {len(buffer)} candles to DB (timeout)")
                        buffer.clear()
                    continue
                except Exception as e:
                    self._logger.error(f"DBIngestionSink worker error: {e}")
        finally:
            if buffer:
                try:
                    await upsert_candles(self._db_path, buffer)
                    self._logger.debug(f"Flushed {len(buffer)} candles to DB (final)")
                except Exception as e:
                    self._logger.error(f"DBIngestionSink final flush error: {e}")
            self._logger.info("DBIngestionSink worker stopped")

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        # Lazily start background worker and DB initialization
        await self._ensure_started()

        # Only store candles for the configured FIGI (ignore others if any)
        figi_to_store = figi or self._figi

        try:
            db_candle = DBCandle.from_candle(figi_to_store, candle)  # type: ignore[arg-type]
            # Non-blocking put with backpressure if queue grows
            await self._queue.put(db_candle)
        except Exception as e:
            self._logger.warning(f"Failed to enqueue candle for DB write: {e}")

    async def on_signal(self, signal: Any, figi: str, price: float) -> None:
        # Signals are not persisted by this sink
        return

    async def on_market_status(self, status: dict) -> None:
        # Market status is not persisted by this sink (could be added later)
        return

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._worker_task:
            try:
                await self._worker_task
            except Exception:
                pass
            self._worker_task = None


