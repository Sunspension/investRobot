import os
import sqlite3
from datetime import datetime

from visualization.services.historical_loader import HistoricalLoader
from visualization.data_manager import VisualizationDataStore


def test_historical_loader_reads_db(tmp_path):
    db_path = tmp_path / 'candles.db'
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS candles (
                time TEXT,
                figi TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO candles(time, figi, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
            (datetime.now().isoformat(), 'TESTFIGI', 1.0, 2.0, 0.5, 1.5, 10),
        )
        conn.commit()

    dm = VisualizationDataStore()
    loader = HistoricalLoader(db_path=str(db_path))
    loader.load_into(dm, 'TESTFIGI', limit=10)

    assert len(dm.candles_data) == 1


