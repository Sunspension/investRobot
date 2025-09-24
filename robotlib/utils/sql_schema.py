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
    account_id TEXT,
    figi TEXT NOT NULL,
    time TEXT NOT NULL,
    type TEXT NOT NULL,         -- buy | sell | short_buy | short_sell | stop_loss_*
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,       -- filled | cancelled | rejected | partially_filled
    commission REAL DEFAULT 0.0,
    strategy TEXT,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_orders_figi_time ON orders(figi, time);

-- Outbox для идемпотентной доставки событий об исполнениях ордеров
CREATE TABLE IF NOT EXISTS order_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    account_id TEXT,
    figi TEXT NOT NULL,
    order_id TEXT,
    payload TEXT NOT NULL,
    delivered INTEGER NOT NULL DEFAULT 0,
    delivered_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_outbox_delivered ON order_outbox(delivered);
"""

async def init_db(db_path: str):
    async with aiosqlite.connect(db_path) as conn:
        # Включаем WAL и базовые параметры для конкурентного чтения/записи
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.executescript(CANDLES_SCHEMA)

        # Простейшая миграция: добавляем недостающие поля в orders
        try:
            cursor = await conn.execute("PRAGMA table_info(orders);")
            cols = [row[1] async for row in cursor]
            if 'order_id' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN order_id TEXT;")
            if 'account_id' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN account_id TEXT;")
            if 'commission' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN commission REAL DEFAULT 0.0;")
            if 'type' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN type TEXT;")
            if 'status' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'filled';")
            if 'reason' not in cols:
                await conn.execute("ALTER TABLE orders ADD COLUMN reason TEXT;")
            # Индексы
            if 'account_id' in cols:
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_account_time ON orders(account_id, time);")
            # Outbox таблица
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS order_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    account_id TEXT,
                    figi TEXT NOT NULL,
                    order_id TEXT,
                    payload TEXT NOT NULL,
                    delivered INTEGER NOT NULL DEFAULT 0,
                    delivered_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_outbox_delivered ON order_outbox(delivered);
                """
            )
        except Exception:
            pass
        await conn.commit()
