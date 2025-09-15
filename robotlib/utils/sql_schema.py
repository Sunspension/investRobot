import aiosqlite

CANDLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    figi TEXT NOT NULL,
    time TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL,
    UNIQUE(figi, time)
);
CREATE INDEX IF NOT EXISTS idx_candles_figi_time ON candles(figi, time);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,
    figi TEXT NOT NULL,
    time TEXT NOT NULL,
    type TEXT NOT NULL,         -- buy | sell | short_buy | short_sell | stop_loss_*
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,       -- filled | cancelled | rejected | partially_filled
    strategy TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_figi_time ON orders(figi, time);
"""

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        await conn.executescript(CANDLES_SCHEMA)
        await conn.commit()
