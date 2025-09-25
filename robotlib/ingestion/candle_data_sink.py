from __future__ import annotations

import asyncio
from typing import Any, Optional

from tinkoff.invest import Candle, HistoricCandle

from robotlib.utils.logger import get_logger
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import DBCandle, upsert_candles
from robotlib.trading_interfaces import CandleEventSinkable


class CandleDataSink(CandleEventSinkable):
    """Приёмник для сохранения свечей в SQLite в фоне.

    Специализируется только на свечах. Игнорирует все остальные события.
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
        # Инициализируем схему БД и запускаем фонового рабочего один раз
        await init_db(self._db_path)
        self._worker_task = asyncio.create_task(self._worker(), name="candle_data_sink_worker")
        self._started = True
        self._logger.info(
            f"CandleDataSink запущен: db_path={self._db_path}, figi={self._figi}, "
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
                        self._logger.debug(f"Сброшено {len(buffer)} свечей в БД")
                        buffer.clear()
                except asyncio.TimeoutError:
                    if buffer:
                        await upsert_candles(self._db_path, buffer)
                        self._logger.debug(f"Сброшено {len(buffer)} свечей в БД (таймаут)")
                        buffer.clear()
                    continue
                except Exception as e:
                    self._logger.error(f"Ошибка фонового сохранения в CandleDataSink: {e}")
        finally:
            if buffer:
                try:
                    await upsert_candles(self._db_path, buffer)
                    self._logger.debug(f"Сброшено {len(buffer)} свечей в БД (финальный сброс)")
                except Exception as e:
                    self._logger.error(f"Ошибка финального сброса CandleDataSink: {e}")
            self._logger.info("Фоновый рабочий CandleDataSink остановлен")

    async def on_candle(self, candle: Any, price: float, figi: str) -> None:
        """Сохраняет свечи в очередь для записи в БД."""
        # Ленивый запуск фонового рабочего и инициализация БД
        await self._ensure_started()

        # Сохраняем свечи только для сконфигурированного FIGI
        figi_to_store = figi or self._figi
        if figi_to_store != self._figi:
            return

        try:
            db_candle = DBCandle.from_candle(figi_to_store, candle)  # type: ignore[arg-type]
            # Неблокирующая постановка в очередь; при росте очереди работает backpressure
            await self._queue.put(db_candle)
        except Exception as e:
            self._logger.warning(f"Не удалось поставить свечу в очередь для записи в БД: {e}")

    async def close(self) -> None:
        """Корректно закрывает sink и останавливает фоновый воркер."""
        if self._closed:
            return
        self._closed = True
        if self._worker_task:
            try:
                await self._worker_task
            except Exception:
                pass
            self._worker_task = None
