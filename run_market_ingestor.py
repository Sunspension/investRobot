import asyncio
import os
import signal
from typing import Optional

from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.ingestion.db_sink import DBIngestionSink
from robotlib.utils.logger import get_logger


logger = get_logger(__name__)


async def _run(figi: str, db_path: str, run_seconds: Optional[int]) -> None:
    cfg = load_config()

    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with TinkoffAPIClient(
        token=cfg.tcs_client.token,
        account_id=cfg.tcs_client.account_id,
        sandbox_token=cfg.tcs_client.sandbox_token,
    ) as api_client:
        stream = MarketDataStream(api_client=api_client, figi=figi)

        # Attach DB ingestion sink
        sink = DBIngestionSink(db_path=db_path, figi=figi)
        stream.set_visualization_sink(sink)

        stop_event = asyncio.Event()

        def _handle_signal(signum, frame):  # type: ignore[no-redef]
            logger.info(f"Received signal {signum}, stopping ingestor...")
            stop_event.set()

        # Register signal handlers
        for s in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(s, _handle_signal)
            except Exception:
                pass

        started = await stream.start()
        if not started:
            logger.error("Не удалось запустить MarketDataStream для инжестора")
            return

        # Optional timeout for controlled runs
        timeout_task: Optional[asyncio.Task] = None
        if run_seconds and run_seconds > 0:
            async def _timeout():
                await asyncio.sleep(run_seconds)
                stop_event.set()
            timeout_task = asyncio.create_task(_timeout())

        try:
            await stop_event.wait()
        finally:
            await stream.stop()
            await sink.close()
            if timeout_task:
                timeout_task.cancel()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Standalone market data ingestor → SQLite")
    parser.add_argument("--figi", default="FUTIMOEXF000", help="Instrument FIGI")
    parser.add_argument("--db", default=os.path.join("data", "candles.db"), help="SQLite DB path")
    parser.add_argument("--seconds", type=int, default=0, help="Run duration in seconds (0 = infinite)")
    args = parser.parse_args()

    logger.info(f"Starting market ingestor for FIGI={args.figi}, DB={args.db}, seconds={args.seconds}")
    asyncio.run(_run(args.figi, args.db, args.seconds if args.seconds > 0 else None))


if __name__ == "__main__":
    main()


