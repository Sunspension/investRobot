from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Iterable

from tinkoff.invest import Candle, HistoricCandle
from robotlib.utils.money import Money


@dataclass
class DBCandle:
    figi: str
    time: datetime  # naive or tz-aware datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @staticmethod
    def from_candle(figi: str, c: Candle | HistoricCandle) -> "DBCandle":
        return DBCandle(
            figi=figi,
            time=c.time,
            open=Money(c.open).to_float(),
            high=Money(c.high).to_float(),
            low=Money(c.low).to_float(),
            close=Money(c.close).to_float(),
            volume=int(Money(c.volume).to_float()),
        )


async def upsert_candles(db_path: str, candles: Iterable[DBCandle]) -> None:
    sql = (
        "INSERT INTO candles (figi, time, open, high, low, close, volume) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(figi, time) DO UPDATE SET "
        "open=excluded.open, high=excluded.high, low=excluded.low, "
        "close=excluded.close, volume=excluded.volume"
    )
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            sql,
            [
                (
                    c.figi,
                    c.time.isoformat(),
                    c.open,
                    c.high,
                    c.low,
                    c.close,
                    c.volume,
                )
                for c in candles
            ],
        )
        await conn.commit()


async def iter_candles(
    db_path: str,
    figi: str,
    from_time: datetime,
    to_time: datetime | None = None,
) -> AsyncIterator[DBCandle]:
    to_clause = ""
    params: list = [figi, from_time.isoformat()]
    if to_time is not None:
        to_clause = " AND time < ?"
        params.append(to_time.isoformat())

    sql = (
        "SELECT figi, time, open, high, low, close, volume "
        "FROM candles WHERE figi = ? AND time >= ?" + to_clause + " ORDER BY time ASC"
    )

    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(sql, params) as cursor:
            async for row in cursor:
                yield DBCandle(
                    figi=row["figi"],
                    time=datetime.fromisoformat(row["time"]),
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
