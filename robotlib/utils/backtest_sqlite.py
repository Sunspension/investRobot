from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime
from typing import Iterable

from tinkoff.invest import HistoricCandle

from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.utils.sql_repository import iter_candles, DBCandle
from robotlib.signal_manager import SignalManager


async def run_backtest_from_sqlite(
    db_path: str,
    figi: str,
    from_time: datetime,
    to_time: datetime,
    strategy_manager: StrategyManager,
) -> dict:
    """
    Читает свечи из SQLite, прогоняет через StrategyManager и возвращает метрики.
    """
    candles: list[DBCandle] = [
        c async for c in iter_candles(db_path=db_path, figi=figi, from_time=from_time, to_time=to_time)
    ]

    prev_day = None
    prev_hc = None
    for c in candles:
        # Конструируем упрощенный суррогат HistoricCandle для совместимости
        class HC:
            pass
        hc = HC()
        hc.time = c.time
        hc.open = c.open
        hc.high = c.high
        hc.low = c.low
        hc.close = c.close
        hc.volume = c.volume

        current_day = c.time.date()

        # Если наступил новый торговый день — закрываем позиции предыдущего дня
        if prev_day is not None and current_day != prev_day and prev_hc is not None:
            strategy_manager.close_position(prev_hc)  # type: ignore

        strategy_manager.on_candle(hc)  # type: ignore

        prev_day = current_day
        prev_hc = hc

    # Закроем позиции последней свечой периода
    if candles:
        class HC:
            pass
        last = candles[-1]
        hc = HC()
        hc.time = last.time
        hc.open = last.open
        hc.high = last.high
        hc.low = last.low
        hc.close = last.close
        hc.volume = last.volume
        strategy_manager.close_position(hc)  # type: ignore

    return {
        "income": strategy_manager.income,
        "trades": strategy_manager.trades,
        "candles": strategy_manager.candles,
    }
