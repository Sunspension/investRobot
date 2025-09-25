#!/usr/bin/env python3
"""
Тесты для sql_repository
"""
import asyncio
import json
import tempfile
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from robotlib.utils.sql_repository import (
    DBCandle, upsert_candles, insert_orders, load_orders,
    outbox_enqueue_order, outbox_fetch_batch, outbox_mark_delivered, iter_candles
)
from robotlib.utils.money import Money


async def create_test_db_schema(db_path: str) -> None:
    """Создает тестовую схему БД для тестов"""
    import aiosqlite
    
    async with aiosqlite.connect(db_path) as conn:
        # Создаем таблицу candles
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                figi TEXT NOT NULL,
                time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume INTEGER NOT NULL,
                PRIMARY KEY (figi, time)
            )
        """)
        
        # Создаем таблицу orders
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT,
                account_id TEXT,
                figi TEXT NOT NULL,
                time TEXT NOT NULL,
                type TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL DEFAULT 'filled',
                commission REAL NOT NULL DEFAULT 0.0,
                strategy TEXT
            )
        """)
        
        # Создаем таблицу order_outbox
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS order_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                account_id TEXT,
                figi TEXT NOT NULL,
                order_id TEXT,
                payload TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                delivered_at TEXT
            )
        """)
        
        await conn.commit()


class TestDBCandle:
    """Тесты для класса DBCandle"""
    
    def test_dbcandle_creation(self):
        """Тест создания DBCandle"""
        now = datetime.now(timezone.utc)
        candle = DBCandle(
            figi="TEST123",
            time=now,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=1000
        )
        
        assert candle.figi == "TEST123"
        assert candle.time == now
        assert candle.open == 100.0
        assert candle.high == 105.0
        assert candle.low == 95.0
        assert candle.close == 102.0
        assert candle.volume == 1000
    
    def test_from_candle_with_candle(self):
        """Тест создания DBCandle из Candle"""
        # Создаем мок Candle с правильными объектами Money
        from robotlib.utils.money import Money
        
        mock_candle = Mock()
        mock_candle.time = datetime.now(timezone.utc)
        mock_candle.open = Money(100, 0)  # 100.0
        mock_candle.high = Money(105, 0)  # 105.0
        mock_candle.low = Money(95, 0)    # 95.0
        mock_candle.close = Money(102, 0) # 102.0
        mock_candle.volume = 1000
        
        db_candle = DBCandle.from_candle("TEST123", mock_candle)
        
        assert db_candle.figi == "TEST123"
        assert db_candle.time == mock_candle.time
        assert db_candle.open == 100.0
        assert db_candle.high == 105.0
        assert db_candle.low == 95.0
        assert db_candle.close == 102.0
        assert db_candle.volume == 1000
    
    def test_from_candle_with_historic_candle(self):
        """Тест создания DBCandle из HistoricCandle"""
        # Создаем мок HistoricCandle с правильными объектами Money
        from robotlib.utils.money import Money
        
        mock_candle = Mock()
        mock_candle.time = datetime.now(timezone.utc)
        mock_candle.open = Money(200, 500000000)  # 200.5
        mock_candle.high = Money(210, 0)          # 210.0
        mock_candle.low = Money(190, 0)           # 190.0
        mock_candle.close = Money(205, 250000000) # 205.25
        mock_candle.volume = 2000
        
        db_candle = DBCandle.from_candle("TEST456", mock_candle)
        
        assert db_candle.figi == "TEST456"
        assert db_candle.time == mock_candle.time
        assert db_candle.open == 200.5  # 200 + 0.5
        assert db_candle.high == 210.0
        assert db_candle.low == 190.0
        assert db_candle.close == 205.25  # 205 + 0.25
        assert db_candle.volume == 2000
    
    def test_from_candle_with_none_volume(self):
        """Тест создания DBCandle с None volume"""
        from robotlib.utils.money import Money
        
        mock_candle = Mock()
        mock_candle.time = datetime.now(timezone.utc)
        mock_candle.open = Money(100, 0)
        mock_candle.high = Money(105, 0)
        mock_candle.low = Money(95, 0)
        mock_candle.close = Money(102, 0)
        mock_candle.volume = None
        
        db_candle = DBCandle.from_candle("TEST123", mock_candle)
        
        assert db_candle.volume == 0  # None должно конвертироваться в 0


class TestUpsertCandles:
    """Тесты для функции upsert_candles"""
    
    @pytest.mark.asyncio
    async def test_upsert_candles_basic(self):
        """Тест базовой вставки свечей"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Создаем тестовые свечи
            now = datetime.now(timezone.utc)
            candles = [
                DBCandle(
                    figi="TEST123",
                    time=now,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000
                ),
                DBCandle(
                    figi="TEST123",
                    time=now.replace(second=now.second + 1),
                    open=102.0,
                    high=108.0,
                    low=98.0,
                    close=106.0,
                    volume=1200
                )
            ]
            
            await upsert_candles(db_path, candles)
            
            # Проверяем что данные записались
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT COUNT(*) as count FROM candles") as cursor:
                    row = await cursor.fetchone()
                    assert row["count"] == 2
                
                async with conn.execute("SELECT * FROM candles WHERE figi = 'TEST123' ORDER BY time") as cursor:
                    rows = await cursor.fetchall()
                    assert len(rows) == 2
                    assert rows[0]["open"] == 100.0
                    assert rows[1]["open"] == 102.0
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_upsert_candles_timezone_handling(self):
        """Тест обработки временных зон"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Тест с naive datetime
            naive_time = datetime.now()
            candle_naive = DBCandle(
                figi="TEST123",
                time=naive_time,
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000
            )
            
            # Тест с timezone-aware datetime
            utc_time = datetime.now(timezone.utc)
            candle_utc = DBCandle(
                figi="TEST456",
                time=utc_time,
                open=200.0,
                high=205.0,
                low=195.0,
                close=202.0,
                volume=2000
            )
            
            await upsert_candles(db_path, [candle_naive, candle_utc])
            
            # Проверяем что данные записались
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT COUNT(*) as count FROM candles") as cursor:
                    row = await cursor.fetchone()
                    assert row["count"] == 2
        
        finally:
            import os
            os.unlink(db_path)


class TestInsertOrders:
    """Тесты для функции insert_orders"""
    
    @pytest.mark.asyncio
    async def test_insert_orders_basic(self):
        """Тест базовой вставки ордеров"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Создаем тестовые ордера
            now = datetime.now(timezone.utc)
            orders = [
                {
                    "order_id": "order_1",
                    "account_id": "acc_123",
                    "figi": "TEST123",
                    "time": now,
                    "type": "buy",
                    "price": 100.0,
                    "quantity": 10,
                    "status": "filled",
                    "commission": 1.0,
                    "strategy": "test_strategy"
                },
                {
                    "order_id": "order_2",
                    "account_id": "acc_123",
                    "figi": "TEST456",
                    "time": now.replace(second=now.second + 1),
                    "type": "sell",
                    "price": 200.0,
                    "quantity": 5,
                    "status": "filled",
                    "commission": 2.0,
                    "strategy": "test_strategy"
                }
            ]
            
            await insert_orders(db_path, orders)
            
            # Проверяем что данные записались
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT COUNT(*) as count FROM orders") as cursor:
                    row = await cursor.fetchone()
                    assert row["count"] == 2
                
                async with conn.execute("SELECT * FROM orders WHERE figi = 'TEST123'") as cursor:
                    row = await cursor.fetchone()
                    assert row["order_id"] == "order_1"
                    assert row["type"] == "buy"
                    assert row["price"] == 100.0
                    assert row["quantity"] == 10
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_insert_orders_empty_list(self):
        """Тест вставки пустого списка ордеров"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Пустой список не должен вызывать ошибок
            await insert_orders(db_path, [])
            
            # Проверяем что ничего не записалось
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT COUNT(*) as count FROM orders") as cursor:
                    row = await cursor.fetchone()
                    assert row["count"] == 0
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_insert_orders_with_defaults(self):
        """Тест вставки ордеров с значениями по умолчанию"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Ордер с минимальными полями
            now = datetime.now(timezone.utc)
            orders = [
                {
                    "figi": "TEST123",
                    "time": now,
                    "type": "buy",
                    "price": 100.0
                    # quantity, status, commission, strategy - отсутствуют
                }
            ]
            
            await insert_orders(db_path, orders)
            
            # Проверяем что данные записались с значениями по умолчанию
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT * FROM orders WHERE figi = 'TEST123'") as cursor:
                    row = await cursor.fetchone()
                    assert row["quantity"] == 1  # Значение по умолчанию
                    assert row["status"] == "filled"  # Значение по умолчанию
                    assert row["commission"] == 0.0  # Значение по умолчанию
                    assert row["strategy"] is None  # Значение по умолчанию
        
        finally:
            import os
            os.unlink(db_path)


class TestLoadOrders:
    """Тесты для функции load_orders"""
    
    @pytest.mark.asyncio
    async def test_load_orders_basic(self):
        """Тест базовой загрузки ордеров"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Сначала вставляем тестовые данные
            now = datetime.now(timezone.utc)
            orders = [
                {
                    "order_id": "order_1",
                    "account_id": "acc_123",
                    "figi": "TEST123",
                    "time": now,
                    "type": "buy",
                    "price": 100.0,
                    "quantity": 10,
                    "status": "filled",
                    "commission": 1.0,
                    "strategy": "test_strategy"
                },
                {
                    "order_id": "order_2",
                    "account_id": "acc_123",
                    "figi": "TEST123",
                    "time": now.replace(second=now.second + 1),
                    "type": "sell",
                    "price": 200.0,
                    "quantity": 5,
                    "status": "filled",
                    "commission": 2.0,
                    "strategy": "test_strategy"
                }
            ]
            
            await insert_orders(db_path, orders)
            
            # Загружаем ордера
            loaded_orders = await load_orders(
                db_path=db_path,
                figi="TEST123",
                from_time=now.replace(second=now.second - 1)
            )
            
            assert len(loaded_orders) == 2
            assert loaded_orders[0]["order_id"] == "order_1"
            assert loaded_orders[1]["order_id"] == "order_2"
            assert loaded_orders[0]["type"] == "buy"
            assert loaded_orders[1]["type"] == "sell"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_load_orders_with_time_range(self):
        """Тест загрузки ордеров с временным диапазоном"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Вставляем тестовые данные
            base_time = datetime.now(timezone.utc)
            orders = [
                {
                    "figi": "TEST123",
                    "time": base_time,
                    "type": "buy",
                    "price": 100.0
                },
                {
                    "figi": "TEST123",
                    "time": base_time.replace(second=base_time.second + 1),
                    "type": "sell",
                    "price": 200.0
                },
                {
                    "figi": "TEST123",
                    "time": base_time.replace(second=base_time.second + 2),
                    "type": "buy",
                    "price": 300.0
                }
            ]
            
            await insert_orders(db_path, orders)
            
            # Загружаем ордера в диапазоне
            loaded_orders = await load_orders(
                db_path=db_path,
                figi="TEST123",
                from_time=base_time,
                to_time=base_time.replace(second=base_time.second + 2)
            )
            
            assert len(loaded_orders) == 2  # Только первые два ордера
        
        finally:
            import os
            os.unlink(db_path)


class TestOutboxFunctions:
    """Тесты для outbox функций"""
    
    @pytest.mark.asyncio
    async def test_outbox_enqueue_order(self):
        """Тест постановки события в outbox"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            payload = {"test": "data", "value": 123}
            
            await outbox_enqueue_order(
                db_path=db_path,
                account_id="acc_123",
                figi="TEST123",
                order_id="order_1",
                payload=payload
            )
            
            # Проверяем что событие записалось
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT COUNT(*) as count FROM order_outbox") as cursor:
                    row = await cursor.fetchone()
                    assert row["count"] == 1
                
                async with conn.execute("SELECT * FROM order_outbox") as cursor:
                    row = await cursor.fetchone()
                    assert row["account_id"] == "acc_123"
                    assert row["figi"] == "TEST123"
                    assert row["order_id"] == "order_1"
                    assert row["delivered"] == 0
                    
                    # Проверяем payload
                    loaded_payload = json.loads(row["payload"])
                    assert loaded_payload == payload
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_outbox_fetch_batch(self):
        """Тест получения батча из outbox"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Добавляем несколько событий
            payload1 = {"test": "data1"}
            payload2 = {"test": "data2"}
            
            await outbox_enqueue_order(
                db_path=db_path,
                account_id="acc_123",
                figi="TEST123",
                order_id="order_1",
                payload=payload1
            )
            
            await outbox_enqueue_order(
                db_path=db_path,
                account_id="acc_456",
                figi="TEST456",
                order_id="order_2",
                payload=payload2
            )
            
            # Получаем батч
            batch = await outbox_fetch_batch(db_path, limit=10)
            
            assert len(batch) == 2
            assert batch[0]["figi"] == "TEST123"
            assert batch[1]["figi"] == "TEST456"
            assert batch[0]["payload"] == payload1
            assert batch[1]["payload"] == payload2
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_outbox_mark_delivered(self):
        """Тест отметки события как доставленного"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Добавляем событие
            payload = {"test": "data"}
            
            await outbox_enqueue_order(
                db_path=db_path,
                account_id="acc_123",
                figi="TEST123",
                order_id="order_1",
                payload=payload
            )
            
            # Получаем событие
            batch = await outbox_fetch_batch(db_path, limit=1)
            assert len(batch) == 1
            event_id = batch[0]["id"]
            
            # Отмечаем как доставленное
            await outbox_mark_delivered(db_path, event_id)
            
            # Проверяем что событие больше не возвращается
            batch = await outbox_fetch_batch(db_path, limit=10)
            assert len(batch) == 0
            
            # Проверяем что в БД событие отмечено как доставленное
            import aiosqlite
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                async with conn.execute("SELECT delivered, delivered_at FROM order_outbox WHERE id = ?", (event_id,)) as cursor:
                    row = await cursor.fetchone()
                    assert row["delivered"] == 1
                    assert row["delivered_at"] is not None
        
        finally:
            import os
            os.unlink(db_path)


class TestIterCandles:
    """Тесты для функции iter_candles"""
    
    @pytest.mark.asyncio
    async def test_iter_candles_basic(self):
        """Тест базовой итерации по свечам"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Вставляем тестовые свечи
            now = datetime.now(timezone.utc)
            candles = [
                DBCandle(
                    figi="TEST123",
                    time=now,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000
                ),
                DBCandle(
                    figi="TEST123",
                    time=now.replace(second=now.second + 1),
                    open=102.0,
                    high=108.0,
                    low=98.0,
                    close=106.0,
                    volume=1200
                )
            ]
            
            await upsert_candles(db_path, candles)
            
            # Итерируемся по свечам
            loaded_candles = []
            async for candle in iter_candles(
                db_path=db_path,
                figi="TEST123",
                from_time=now.replace(second=now.second - 1)
            ):
                loaded_candles.append(candle)
            
            assert len(loaded_candles) == 2
            assert loaded_candles[0].open == 100.0
            assert loaded_candles[1].open == 102.0
            assert loaded_candles[0].figi == "TEST123"
            assert loaded_candles[1].figi == "TEST123"
        
        finally:
            import os
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_iter_candles_with_time_range(self):
        """Тест итерации по свечам с временным диапазоном"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Создаем схему БД
            await create_test_db_schema(db_path)
            # Вставляем тестовые свечи
            base_time = datetime.now(timezone.utc)
            candles = [
                DBCandle(
                    figi="TEST123",
                    time=base_time,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=102.0,
                    volume=1000
                ),
                DBCandle(
                    figi="TEST123",
                    time=base_time.replace(second=base_time.second + 1),
                    open=102.0,
                    high=108.0,
                    low=98.0,
                    close=106.0,
                    volume=1200
                ),
                DBCandle(
                    figi="TEST123",
                    time=base_time.replace(second=base_time.second + 2),
                    open=106.0,
                    high=110.0,
                    low=100.0,
                    close=108.0,
                    volume=1300
                )
            ]
            
            await upsert_candles(db_path, candles)
            
            # Итерируемся по свечам в диапазоне
            loaded_candles = []
            async for candle in iter_candles(
                db_path=db_path,
                figi="TEST123",
                from_time=base_time,
                to_time=base_time.replace(second=base_time.second + 2)
            ):
                loaded_candles.append(candle)
            
            assert len(loaded_candles) == 2  # Только первые две свечи
        
        finally:
            import os
            os.unlink(db_path)
