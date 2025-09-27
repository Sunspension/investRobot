"""
Расширенная схема БД для работы с API Tinkoff как источником правды
"""

import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Основная схема БД
ENHANCED_SCHEMA = """
-- Таблица операций (основная - копия из API)
CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,                    -- ID операции из API
    operation_type INTEGER NOT NULL,        -- Тип операции (15, 16, 19, etc.)
    date TEXT NOT NULL,                     -- Дата операции
    figi TEXT NOT NULL,                     -- Инструмент
    instrument_type TEXT,                   -- Тип инструмента
    quantity INTEGER NOT NULL,              -- Количество
    quantity_rest INTEGER DEFAULT 0,        -- Остаток количества
    price_currency TEXT,                    -- Валюта цены
    price_units INTEGER,                    -- Целая часть цены
    price_nano INTEGER,                     -- Дробная часть цены
    payment_currency TEXT,                  -- Валюта платежа
    payment_units INTEGER,                  -- Целая часть платежа
    payment_nano INTEGER,                   -- Дробная часть платежа
    commission_currency TEXT,               -- Валюта комиссии
    commission_units INTEGER,               -- Целая часть комиссии
    commission_nano INTEGER,                -- Дробная часть комиссии
    operation_description TEXT,             -- Описание операции
    state INTEGER,                          -- Состояние операции
    parent_operation_id TEXT,               -- ID родительской операции
    position_uid TEXT,                      -- UID позиции
    instrument_uid TEXT,                    -- UID инструмента
    asset_uid TEXT,                         -- UID актива
    created_at TEXT NOT NULL,               -- Время создания записи
    updated_at TEXT NOT NULL                -- Время обновления записи
);

-- Таблица сделок (детали операций)
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,              -- ID сделки из API
    operation_id TEXT NOT NULL,             -- Связь с операцией
    date_time TEXT NOT NULL,                -- Время сделки
    quantity INTEGER NOT NULL,              -- Количество
    price_currency TEXT,                    -- Валюта цены
    price_units INTEGER,                    -- Целая часть цены
    price_nano INTEGER,                     -- Дробная часть цены
    created_at TEXT NOT NULL,               -- Время создания записи
    FOREIGN KEY (operation_id) REFERENCES operations(id) ON DELETE CASCADE
);

-- Таблица ордеров (агрегированные данные для удобства)
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT UNIQUE,                   -- ID ордера (может быть operation_id)
    account_id TEXT,                        -- ID счета
    figi TEXT NOT NULL,                     -- Инструмент
    time TEXT NOT NULL,                     -- Время ордера
    direction TEXT NOT NULL,                -- buy/sell
    price REAL NOT NULL,                    -- Цена в рублях (конвертированная)
    quantity INTEGER NOT NULL,              -- Количество
    status TEXT NOT NULL,                   -- filled/cancelled/rejected
    commission REAL DEFAULT 0.0,            -- Комиссия в рублях
    strategy TEXT,                          -- Стратегия
    reason TEXT,                            -- Причина
    operation_id TEXT,                      -- Связь с операцией
    trade_id TEXT,                          -- Связь со сделкой
    execution_time TEXT,                    -- Время исполнения
    created_at TEXT NOT NULL,               -- Время создания записи
    updated_at TEXT NOT NULL,               -- Время обновления записи
    FOREIGN KEY (operation_id) REFERENCES operations(id)
);

-- Таблица синхронизации (отслеживание состояния)
CREATE TABLE IF NOT EXISTS sync_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT NOT NULL,                -- operations, orders, trades
    last_sync_date TEXT,                    -- Последняя дата синхронизации
    last_operation_id TEXT,                 -- Последний обработанный ID
    sync_status TEXT NOT NULL,              -- success, error, in_progress
    error_message TEXT,                     -- Сообщение об ошибке
    created_at TEXT NOT NULL,               -- Время создания записи
    updated_at TEXT NOT NULL                -- Время обновления записи
);

-- Индексы для производительности
CREATE INDEX IF NOT EXISTS idx_operations_figi_date ON operations(figi, date);
CREATE INDEX IF NOT EXISTS idx_operations_type_date ON operations(operation_type, date);
CREATE INDEX IF NOT EXISTS idx_trades_operation_id ON trades(operation_id);
CREATE INDEX IF NOT EXISTS idx_trades_date_time ON trades(date_time);
CREATE INDEX IF NOT EXISTS idx_orders_figi_time ON orders(figi, time);
CREATE INDEX IF NOT EXISTS idx_orders_account_time ON orders(account_id, time);
CREATE INDEX IF NOT EXISTS idx_orders_operation_id ON orders(operation_id);
CREATE INDEX IF NOT EXISTS idx_sync_status_type ON sync_status(sync_type);
"""

# Модели данных
@dataclass
class Operation:
    """Модель операции (копия из API)"""
    id: str
    operation_type: int
    date: datetime
    figi: str
    instrument_type: Optional[str] = None
    quantity: int = 0
    quantity_rest: int = 0
    price_currency: Optional[str] = None
    price_units: Optional[int] = None
    price_nano: Optional[int] = None
    payment_currency: Optional[str] = None
    payment_units: Optional[int] = None
    payment_nano: Optional[int] = None
    commission_currency: Optional[str] = None
    commission_units: Optional[int] = None
    commission_nano: Optional[int] = None
    operation_description: Optional[str] = None
    state: Optional[int] = None
    parent_operation_id: Optional[str] = None
    position_uid: Optional[str] = None
    instrument_uid: Optional[str] = None
    asset_uid: Optional[str] = None

@dataclass
class Trade:
    """Модель сделки (копия из API)"""
    trade_id: str
    operation_id: str
    date_time: datetime
    quantity: int
    price_currency: Optional[str] = None
    price_units: Optional[int] = None
    price_nano: Optional[int] = None

@dataclass
class Order:
    """Модель ордера (агрегированные данные)"""
    order_id: str
    account_id: Optional[str] = None
    figi: str = ""
    time: datetime = None
    direction: str = ""
    price: float = 0.0
    quantity: int = 0
    status: str = "filled"
    commission: float = 0.0
    strategy: Optional[str] = None
    reason: Optional[str] = None
    operation_id: Optional[str] = None
    trade_id: Optional[str] = None
    execution_time: Optional[datetime] = None

@dataclass
class SyncStatus:
    """Статус синхронизации"""
    sync_type: str
    last_sync_date: Optional[datetime] = None
    last_operation_id: Optional[str] = None
    sync_status: str = "pending"
    error_message: Optional[str] = None

async def init_enhanced_db(db_path: str):
    """Инициализация расширенной БД"""
    async with aiosqlite.connect(db_path) as conn:
        # Включаем WAL и базовые параметры
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA synchronous=NORMAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute("PRAGMA foreign_keys=ON;")
        
        # Создаем схему
        await conn.executescript(ENHANCED_SCHEMA)
        
        # Миграция существующих данных
        await _migrate_existing_data(conn)
        
        await conn.commit()

async def _migrate_existing_data(conn: aiosqlite.Connection):
    """Миграция существующих данных из старой схемы"""
    try:
        # Проверяем, есть ли старая таблица orders
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders_old';") as cur:
            old_table_exists = await cur.fetchone()
        
        if not old_table_exists:
            # Переименовываем старую таблицу
            await conn.execute("ALTER TABLE orders RENAME TO orders_old;")
            
            # Создаем новую таблицу orders
            await conn.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT UNIQUE,
                    account_id TEXT,
                    figi TEXT NOT NULL,
                    time TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    commission REAL DEFAULT 0.0,
                    strategy TEXT,
                    reason TEXT,
                    operation_id TEXT,
                    trade_id TEXT,
                    execution_time TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            
            # Копируем данные из старой таблицы
            await conn.execute("""
                INSERT INTO orders (
                    order_id, account_id, figi, time, direction, price, quantity, 
                    status, commission, strategy, reason, created_at, updated_at
                )
                SELECT 
                    order_id, account_id, figi, time, direction, price, quantity,
                    status, commission, strategy, reason, 
                    datetime('now'), datetime('now')
                FROM orders_old;
            """)
            
            # Удаляем старую таблицу
            await conn.execute("DROP TABLE orders_old;")
            
            print("✅ Миграция данных завершена")
            
    except Exception as e:
        print(f"⚠️ Ошибка миграции: {e}")

# Утилиты для работы с MoneyValue
def money_value_to_dict(money_value) -> Dict[str, Any]:
    """Конвертирует MoneyValue в словарь"""
    if money_value is None:
        return {"currency": None, "units": None, "nano": None}
    
    return {
        "currency": getattr(money_value, 'currency', None),
        "units": getattr(money_value, 'units', None),
        "nano": getattr(money_value, 'nano', None)
    }

def dict_to_money_value(money_dict: Dict[str, Any]):
    """Конвертирует словарь в MoneyValue"""
    if not money_dict or money_dict.get("currency") is None:
        return None
    
    # Создаем объект MoneyValue (нужно импортировать из tinkoff.invest)
    from tinkoff.invest.schemas import MoneyValue
    return MoneyValue(
        currency=money_dict["currency"],
        units=money_dict["units"] or 0,
        nano=money_dict["nano"] or 0
    )

def convert_money_to_rubles(money_dict: Dict[str, Any], point_value: float = 1.0) -> float:
    """Конвертирует MoneyValue в рубли"""
    if not money_dict or money_dict.get("currency") is None:
        return 0.0
    
    units = money_dict.get("units", 0) or 0
    nano = money_dict.get("nano", 0) or 0
    currency = money_dict.get("currency", "rub")
    
    # Конвертируем в float
    value = float(units) + float(nano) / 1_000_000_000
    
    # Конвертируем в рубли
    if currency == "pt.":
        return value * point_value
    elif currency == "usd":
        # Здесь нужно добавить курс валют
        return value * 100.0  # Примерный курс
    else:  # rub
        return value
