import datetime as dt

import pandas as pd

from visualization.data_manager import DataManager


def test_load_historical_today_and_cap(monkeypatch, tmp_path):
    db = tmp_path / "market.db"
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE candles (figi TEXT, time TEXT, open REAL, high REAL, low REAL, close REAL, volume INTEGER)"
        )
        # вставим вчера и сегодня; сегодня > 210 баров
        msk = dt.timezone(dt.timedelta(hours=3))
        today = dt.datetime.now(msk).date()
        yesterday = today - dt.timedelta(days=1)
        # 5 баров вчера
        for i in range(5):
            t = dt.datetime.combine(yesterday, dt.time(10, 0)) + dt.timedelta(minutes=i)
            conn.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
                ("F1", t.isoformat(), 1, 2, 0.5, 1.5, 10),
            )
        # 210 баров сегодня
        for i in range(210):
            t = dt.datetime.combine(today, dt.time(10, 0)) + dt.timedelta(minutes=i)
            conn.execute(
                "INSERT INTO candles VALUES (?,?,?,?,?,?,?)",
                ("F1", t.isoformat(), 1, 2, 0.5, 1.5, 10),
            )
        conn.commit()

    dm = DataManager()
    dm.load_historical_candles(str(db), "F1", limit=500)
    snap = dm.get_data_snapshot()
    # Только сегодня (лимит больше не режем до 200 в загрузке)
    assert len(snap["candles_data"]) == 210
    assert all(c["time"].date() == snap["candles_data"][-1]["time"].date() for c in snap["candles_data"])


