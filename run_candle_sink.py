import asyncio
import os
import signal
from typing import Optional

from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.trading.market_data_stream import MarketDataStream
from robotlib.trading.candle_cache import CandleCache
from robotlib.trading.historical_data_loader import HistoricalDataLoader
from robotlib.trading.stream_watchdog import StreamWatchdog
from robotlib.trading.stream_registry import get_stream_registry
from robotlib.ingestion.candle_data_sink import CandleDataSink
from robotlib.utils.logger import get_logger, setup_logging
from robotlib.utils.backoff import compute_backoff_delay
import logging


# Настраиваем логирование с датой
setup_logging(level=logging.INFO, log_file='data/logs/candle_sink.log')
logger = get_logger(__name__)


async def _run_candle_sink(figi: str, db_path: str, run_seconds: Optional[int]) -> None:
    """Запускает CandleDataSink для сбора и сохранения свечей в SQLite"""
    cfg = load_config()

    # Ensure data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with TinkoffAPIClient(
        token=cfg.tcs_client.token,
        account_id=cfg.tcs_client.account_id,
        sandbox_token=cfg.tcs_client.sandbox_token,
    ) as api_client:
        # Проверяем реестр стримов для переиспользования
        registry = get_stream_registry()
        existing_stream = registry.get_stream(figi)
        
        if existing_stream:
            logger.info(f"Переиспользуем существующий стрим для {figi}")
            stream = existing_stream
        else:
            # Создаем компоненты для MarketDataStream
            candle_cache = CandleCache(cache_size=100)
            historical_loader = HistoricalDataLoader(api_client, figi)
            watchdog = (
                StreamWatchdog(
                    stale_seconds=cfg.watchdog_stale_seconds,
                    require_open_market=cfg.watchdog_require_open_market,
                    check_interval=getattr(cfg, 'watchdog_check_interval', 30),
                )
                if getattr(cfg, 'watchdog_enabled', True)
                else None
            )
            
            stream = MarketDataStream(
                api_client=api_client,
                figi=figi,
                candle_cache=candle_cache,
                historical_loader=historical_loader,
                watchdog=watchdog,
            )
            
            # Регистрируем стрим в реестре
            subscriber_id = f"candle_sink_{id(stream)}"
            stream = registry.register_stream(figi, stream, subscriber_id)

        candle_sink = CandleDataSink(db_path=db_path, figi=figi)
        stream.set_event_sink(candle_sink)
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

        # Optional timeout for controlled runs
        timeout_task: Optional[asyncio.Task] = None
        if run_seconds and run_seconds > 0:
            async def _timeout():
                await asyncio.sleep(run_seconds)
                stop_event.set()
            timeout_task = asyncio.create_task(_timeout())

        # Перезапуск стрима с экспоненциальным бэкоффом как в ядре
        retries = 0
        try:
            while not stop_event.is_set():
                try:
                    ok = await stream.start()
                except Exception as e:
                    logger.warning(f"Ошибка старта стрима: {e}")
                    ok = False

                if not ok:
                    # Принудительно останавливаем стрим перед повторной попыткой
                    try:
                        await stream.stop()
                        # Дополнительная задержка для корректного закрытия соединения
                        await asyncio.sleep(2.0)
                    except Exception as e:
                        logger.warning(f"Ошибка остановки стрима: {e}")
                    
                    delay = compute_backoff_delay(retries, base_seconds=0.5, max_seconds=30.0, jitter="full")
                    logger.info(f"Повторный запуск через {delay:.2f}с (попытка {retries+1})")
                    await asyncio.sleep(delay)
                    retries += 1
                    continue

                # Успешный старт: ждём стоп или падение стрима
                retries = 0
                while not stop_event.is_set():
                    await asyncio.sleep(5)
                    if not stream.is_running:
                        logger.warning("Стрим остановился — перезапускаем")
                        # Принудительно останавливаем стрим перед перезапуском
                        try:
                            await stream.stop()
                            # Дополнительная задержка для корректного закрытия соединения
                            await asyncio.sleep(2.0)
                        except Exception as e:
                            logger.warning(f"Ошибка остановки стрима при перезапуске: {e}")
                        break

            # Вышли из внешнего цикла — остановка
        finally:
            try:
                await stream.stop()
            finally:
                await candle_sink.close()
                if timeout_task:
                    timeout_task.cancel()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Standalone CandleDataSink → SQLite")
    parser.add_argument("--figi", default="FUTIMOEXF000", help="Instrument FIGI")
    parser.add_argument("--db", default=os.path.join("data", "market.db"), help="SQLite DB path")
    parser.add_argument("--seconds", type=int, default=0, help="Run duration in seconds (0 = infinite)")
    args = parser.parse_args()

    logger.info(f"Старт CandleDataSink: FIGI={args.figi}, БД={args.db}, секунд={args.seconds}")
    asyncio.run(_run_candle_sink(args.figi, args.db, args.seconds if args.seconds > 0 else None))


if __name__ == "__main__":
    main()


