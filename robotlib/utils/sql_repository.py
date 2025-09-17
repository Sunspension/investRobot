from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Iterable, List, Dict, Any, Optional

from tinkoff.invest import Candle, HistoricCandle
import json
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


async def insert_orders(db_path: str, orders: List[Dict[str, Any]]) -> None:
    """Вставляет список исполненных ордеров.
    Ожидаемые поля: order_id (optional), figi, time (datetime), type, price, quantity, status, strategy(optional)
    """
    if not orders:
        return
    sql = (
        "INSERT OR IGNORE INTO orders (order_id, account_id, figi, time, type, price, quantity, status, commission, strategy) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    async with aiosqlite.connect(db_path) as conn:
        await conn.executemany(
            sql,
            [
                (
                    o.get("order_id"),
                    o.get("account_id"),
                    o["figi"],
                    (o["time"].isoformat() if isinstance(o["time"], datetime) else str(o["time"])),
                    o["type"],
                    float(o["price"]),
                    int(o.get("quantity", 1)),
                    o.get("status", "filled"),
                    float(o.get("commission", 0.0)),
                    o.get("strategy"),
                )
                for o in orders
            ],
        )
        await conn.commit()


async def load_orders(
    db_path: str,
    figi: str,
    from_time: datetime,
    to_time: datetime | None = None,
    account_id: str | None = None,
) -> List[Dict[str, Any]]:
    to_clause = ""
    where_acc = ""
    params: list = [figi, from_time.isoformat()]
    if to_time is not None:
        to_clause = " AND time < ?"
        params.append(to_time.isoformat())
    if account_id is not None:
        where_acc = " AND account_id = ?"
        params.append(account_id)

    sql = (
        "SELECT order_id, account_id, figi, time, type, price, quantity, status, commission, strategy "
        "FROM orders WHERE figi = ? AND time >= ?" + to_clause + where_acc + " ORDER BY time ASC"
    )
    rows: List[Dict[str, Any]] = []
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(sql, params) as cursor:
            async for row in cursor:
                rows.append({
                    "order_id": row["order_id"],
                    "account_id": row["account_id"],
                    "figi": row["figi"],
                    "time": datetime.fromisoformat(row["time"]),
                    "type": row["type"],
                    "price": row["price"],
                    "quantity": row["quantity"],
                    "status": row["status"],
                    "commission": row["commission"],
                    "strategy": row["strategy"],
                })
    return rows


# Outbox helpers
async def outbox_enqueue_order(
    db_path: str,
    *,
    account_id: Optional[str],
    figi: str,
    order_id: Optional[str],
    payload: Dict[str, Any],
) -> None:
    """Ставит событие об исполнении ордера в outbox."""
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "INSERT INTO order_outbox (created_at, account_id, figi, order_id, payload, delivered) VALUES (?, ?, ?, ?, ?, 0)",
            (
                datetime.now(timezone.utc).isoformat(),
                account_id,
                figi,
                order_id,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        await conn.commit()


async def outbox_fetch_batch(db_path: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Возвращает недоставленные события из outbox."""
    res: List[Dict[str, Any]] = []
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT id, created_at, account_id, figi, order_id, payload FROM order_outbox WHERE delivered = 0 ORDER BY id ASC LIMIT ?",
            (limit,),
        ) as cur:
            async for row in cur:
                res.append({
                    "id": row["id"],
                    "created_at": datetime.fromisoformat(row["created_at"]),
                    "account_id": row["account_id"],
                    "figi": row["figi"],
                    "order_id": row["order_id"],
                    "payload": json.loads(row["payload"]),
                })
    return res


async def outbox_mark_delivered(db_path: str, event_id: int) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            "UPDATE order_outbox SET delivered = 1, delivered_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), event_id),
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
