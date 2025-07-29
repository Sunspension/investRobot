from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from tinkoff.invest import CandleInterval

from robotlib.utils.client import AsyncInvestClient
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import DBCandle, upsert_candles


async def load_month_candles_to_db(
    app_name: str,
    account_id: str,
    token: str,
    sandbox_token: str | None,
    db_path: str,
    figi: str,
    start_date_inclusive: datetime,
) -> int:
    """
    Загружает свечи за месяц (с start_date по start_date + 30 дней) и сохраняет в SQLite.
    Возвращает количество сохраненных свечей.
    """
    await init_db(db_path)

    end_date = start_date_inclusive + timedelta(days=30)

    saved = 0
    async with AsyncInvestClient(
        app_name=app_name,
        account_id=account_id,
        token=token,
        sandbox_token=sandbox_token,
        sandbox_mode=True,
    ) as client:
        candles_batch: list[DBCandle] = []
        async for candle in await client.get_all_candles(
            from_=start_date_inclusive,
            to=end_date,
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN,
            figi=figi,
        ):
            candles_batch.append(DBCandle.from_candle(figi, candle))
            if len(candles_batch) >= 1000:
                await upsert_candles(db_path, candles_batch)
                saved += len(candles_batch)
                candles_batch.clear()
        if candles_batch:
            await upsert_candles(db_path, candles_batch)
            saved += len(candles_batch)

    return saved
