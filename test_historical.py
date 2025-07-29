#!/usr/bin/env python3
"""
Тестовый скрипт для проверки новой архитектуры OrderIntent → OrderExecution
на исторических данных
"""
import asyncio
import sys
import os
from datetime import datetime
from robotlib.utils.logger import get_logger

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_data.config import load_config
from tinkoff.invest.exceptions import InvestError
from tinkoff.invest import CandleInterval
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.signal_manager import SignalManager, OrderDirection, OrderType, OrderStatus
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from tests.mocks import MockOrderExecutor, MockAPIClient, MockPortfolioManager
from robotlib.utils.sql_repository import iter_candles
from robotlib.utils.sql_schema import init_db
import pytz

logger = get_logger(__name__)

# Настраиваем уровень логирования для консоли
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def test_historical_data_with_new_architecture(
    from_time: str = "2025-01-15 7:00",
    to_time: str = "2025-01-15 19:00",
    use_database: bool = False,
    db_path: str = "data/market.db"
):
    """
    Тестирует новую архитектуру OrderIntent → OrderExecution на исторических данных
    """
    logger.info("🚀 Запуск тестирования новой архитектуры на исторических данных")
    
    # Загружаем конфигурацию
    config = load_config()
    token = config.tcs_client.token
    account_id = config.tcs_client.id
    sandbox_token = config.tcs_client.sandbox_token
    
    from_time_dt = _to_msk_date(from_time)
    to_time_dt = _to_msk_date(to_time)
    figi = "FUTIMOEXF000"
    
    # Загружаем исторические данные
    logger.info(f"📊 Загружаем исторические данные с {from_time} по {to_time}")
    
    if use_database:
        # Загружаем из базы данных SQLite
        logger.info("🗄️ Загружаем данные из базы данных...")
        try:
            await init_db(db_path)
            db_candles = [candle async for candle in iter_candles(db_path, figi, from_time_dt, to_time_dt)]
            
            # Конвертируем DBCandle в совместимый формат (как в backtest_sqlite.py)
            historical_candles = []
            for c in db_candles:
                class HC:
                    pass
                hc = HC()
                hc.time = c.time
                hc.open = c.open
                hc.high = c.high
                hc.low = c.low
                hc.close = c.close
                hc.volume = c.volume
                historical_candles.append(hc)
            
            logger.info(f"✅ Загружено {len(historical_candles)} свечей из базы данных")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки из базы данных: {e}")
            logger.info("🔄 Переключаемся на загрузку через API...")
            use_database = False
    
    if not use_database:
        # Загружаем через Tinkoff API
        logger.info("🌐 Загружаем данные через Tinkoff API...")
        async with TinkoffAPIClient(token, account_id, sandbox_token) as api_client:
            historical_candles = [item async for item in _load_historic_data(api_client, figi, from_time_dt, to_time_dt)]
        logger.info(f"✅ Загружено {len(historical_candles)} свечей через API")
    
    if not historical_candles:
        logger.error("❌ Нет исторических данных для тестирования")
        return
    
    # Создаем мок API клиент для тестирования
    async with MockAPIClient(deposit=400000) as mock_api_client:
        portfolio_manager = MockPortfolioManager(mock_api_client)
        
        # Создаем OrderExecutor для тестирования
        # Всегда используем MockOrderExecutor для тестирования, так как реальный API может быть недоступен
        order_executor = MockOrderExecutor(
            success_rate=1.0,
            commission_rate=0.01,
            mock_prices={figi: 1500.0}  # Базовая цена для фьючерса
        )
        
        # Создаем компоненты системы
        risk_limits = RiskLimits(
            max_daily_loss=40000,
            max_position_size=200000,
            percent_from_deposit=50,
            items_per_trade=20,  # Убеждаемся, что не 0
            stop_loss_threshold=5.0
        )
        
        # Создаем менеджеры
        signal_manager = SignalManager()
        risk_manager = RiskManager(risk_limits=risk_limits, portfolio_manager=portfolio_manager)
        
        strategies = [
            LongStrategy(risk_manager, portfolio_manager),
            ShortStrategy(risk_manager, portfolio_manager)
        ]
        
        # Создаем StrategyManager с OrderExecutor
        strategy_manager = StrategyManager(
            signal_manager=signal_manager,
            risk_manager=risk_manager,
            portfolio_manager=portfolio_manager,
            order_executor=order_executor,  # ✅ Передаем OrderExecutor
            strategies=strategies
        )
        
        # Инициализируем стратегии
        await strategy_manager.initialize(figi, point_value=1.0, contracts_per_lot=10)
        
        logger.info("🔄 Начинаем обработку исторических свечей...")
        
        # Обрабатываем каждую свечу
        for i, candle in enumerate(historical_candles):
            await strategy_manager.on_candle(candle)
            
            if i % 100 == 0:  # Показываем прогресс каждые 100 свечей
                logger.info(f"📈 Обработано {i+1}/{len(historical_candles)} свечей")
        
        # Закрываем все позиции в конце
        await strategy_manager.close_all_positions()
        
        # Выводим результаты
        result = {
            'income': strategy_manager.income,
            'trades_count': len(strategy_manager.trades),
            'candles_count': len(historical_candles),
            'executions_count': len(order_executor._executions),
            'long_income': strategies[0].income,
            'short_income': strategies[1].income
        }
        
        logger.info(f"📊 Результаты тестирования: {result}")
        return result

async def _load_historic_data(client: TinkoffAPIClient, figi: str, from_time: datetime, to_time: datetime = None):
    """Загружает исторические данные через Tinkoff API"""
    try:
        response = await client.get_candles(
            figi=figi,
            from_date=from_time,
            to_date=to_time,
            interval=CandleInterval.CANDLE_INTERVAL_1_MIN
        )
        if response and response.candles:
            for candle in response.candles:
                yield candle
    except InvestError as error:
        logger.error(f'Ошибка загрузки исторических данных: {error}', exc_info=True)


def _to_msk_date(date: str, tz_info=False) -> datetime:
    """Конвертирует строку даты в московское время"""
    dt_naive = datetime.strptime(date, "%Y-%m-%d %H:%M")
    moscow_tz = pytz.timezone("Europe/Moscow")
    dt_moscow = moscow_tz.localize(dt_naive)
    return dt_moscow if tz_info else dt_moscow.replace(tzinfo=None)

async def main():
    """Главная функция для запуска тестирования"""
    logger.info("🎯 Тестирование новой архитектуры OrderIntent → OrderExecution")
    
    # Тест 1: Из базы данных
    try:
        logger.info("🧪 Тест 1: Из базы данных SQLite")
        result1 = await test_historical_data_with_new_architecture(
            from_time="2024-12-02 7:00",  # Используем реальные даты из базы
            to_time="2024-12-02 19:00",
            use_database=True,
            db_path="data/market.db"
        )
        logger.info(f"✅ Тест 1 завершен: {result1}")
    except Exception as e:
        logger.error(f"❌ Тест 1 не удался: {e}")
        import traceback
        traceback.print_exc()
    
    # Тест 2: С реальным API
    try:
        logger.info("🧪 Тест 2: С реальным Tinkoff API")
        result2 = await test_historical_data_with_new_architecture(
            from_time="2025-01-15 7:00",
            to_time="2025-01-15 19:00",
            use_database=False
        )
        logger.info(f"✅ Тест 2 завершен: {result2}")
    except Exception as e:
        logger.error(f"❌ Тест 2 не удался: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
