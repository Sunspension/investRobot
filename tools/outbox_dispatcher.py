#!/usr/bin/env python3
import asyncio
import json
import os

from robotlib.utils.logger import get_logger
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import outbox_fetch_batch, outbox_mark_delivered

logger = get_logger(__name__)


async def deliver(payload: dict) -> bool:
    """Заглушка доставки события. Пока просто логируем.
    Верните True при успехе доставки, False при временной ошибке для ретрая.
    """
    try:
        logger.info(f"Доставка outbox-события: {json.dumps(payload, ensure_ascii=False)[:500]}")
        return True
    except Exception as e:
        logger.error(f"Ошибка доставки: {e}")
        return False


async def run_dispatcher(
    db_path: str,
    *,
    batch_size: int = 100,
    interval_sec: float = 1.0,
    once: bool = False,
) -> None:
    await init_db(db_path)
    logger.info(
        f"Запуск outbox-dispatcher: db={db_path}, batch_size={batch_size}, interval={interval_sec}, once={once}"
    )
    while True:
        batch = await outbox_fetch_batch(db_path, limit=batch_size)
        if not batch:
            if once:
                break
            await asyncio.sleep(interval_sec)
            continue
        delivered_any = False
        for event in batch:
            ok = await deliver(event["payload"])  # type: ignore[index]
            if ok:
                await outbox_mark_delivered(db_path, event["id"])  # type: ignore[index]
                delivered_any = True
        if once:
            break
        if not delivered_any:
            await asyncio.sleep(interval_sec)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Outbox dispatcher for order executions")
    parser.add_argument("--db", default=os.path.join("data", "market.db"), help="SQLite DB path")
    parser.add_argument("--batch", type=int, default=100, help="Batch size")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval seconds")
    parser.add_argument("--once", action="store_true", help="Run single cycle and exit")
    args = parser.parse_args()

    asyncio.run(
        run_dispatcher(
            db_path=args.db,
            batch_size=args.batch,
            interval_sec=args.interval,
            once=args.once,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
