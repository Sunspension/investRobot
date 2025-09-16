import asyncio
from datetime import datetime

from tools.outbox_dispatcher import run_dispatcher
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import outbox_enqueue_order, outbox_fetch_batch


def test_outbox_dispatcher_once(tmp_path, monkeypatch):
    db_path = tmp_path / "market.db"
    asyncio.run(init_db(str(db_path)))

    # Подготовим одно событие в outbox
    asyncio.run(outbox_enqueue_order(str(db_path), account_id="ACC", figi="TEST", order_id="OID", payload={"x": 1}))

    called = {"count": 0}

    async def fake_deliver(payload):
        called["count"] += 1
        return True

    import tools.outbox_dispatcher as mod
    monkeypatch.setattr(mod, "deliver", fake_deliver)

    asyncio.run(run_dispatcher(str(db_path), batch_size=10, interval_sec=0.01, once=True))

    assert called["count"] == 1
    # Убеждаемся, что теперь очередь пуста
    batch = asyncio.run(outbox_fetch_batch(str(db_path), limit=10))
    assert len(batch) == 0


