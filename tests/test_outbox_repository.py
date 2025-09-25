import sqlite3
from datetime import datetime, timezone

from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import (
    insert_orders,
    outbox_enqueue_order,
    outbox_fetch_batch,
    outbox_mark_delivered,
)


def test_outbox_roundtrip_and_orders_commission(tmp_path):
    db_path = tmp_path / "market.db"

    # Инициализация БД
    import asyncio
    asyncio.run(init_db(str(db_path)))

    # Вставка ордера с commission и account_id
    order = {
        "order_id": "OID-1",
        "account_id": "ACC-1",
        "figi": "TESTFIGI",
        "time": datetime.now(timezone.utc),
        "direction": "buy",
        "price": 123.45,
        "quantity": 2,
        "status": "filled",
        "commission": 0.67,
        "strategy": "unit-test",
    }
    asyncio.run(insert_orders(str(db_path), [order]))

    # Проверяем, что commission и account_id записались
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT order_id, account_id, price, commission FROM orders WHERE order_id=?",
            (order["order_id"],),
        ).fetchone()
        assert row is not None
        assert row[0] == "OID-1"
        assert row[1] == "ACC-1"
        assert abs(row[2] - 123.45) < 1e-9
        assert abs(row[3] - 0.67) < 1e-9

    # Outbox: enqueue → fetch → mark delivered
    asyncio.run(outbox_enqueue_order(str(db_path), account_id="ACC-1", figi="TESTFIGI", order_id="OID-1", payload={"ok": True}))
    batch = asyncio.run(outbox_fetch_batch(str(db_path), limit=10))
    assert len(batch) == 1
    asyncio.run(outbox_mark_delivered(str(db_path), batch[0]["id"]))
    batch2 = asyncio.run(outbox_fetch_batch(str(db_path), limit=10))
    assert len(batch2) == 0


