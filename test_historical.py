#!/usr/bin/env python3
"""
Тестовый скрипт для проверки архитектуры OrderIntent → OrderExecution
на исторических данных

Архитектура:
1. Стратегии создают OrderIntent (намерение на сделку)
2. StrategyManager получает OrderIntent от стратегий
3. OrderExecutor.execute_order() выполняет ордер
4. Создается OrderExecution с результатами исполнения
5. StrategyManager передает OrderExecution в стратегии
6. Стратегии обрабатывают результат через _process_execution()
"""
import asyncio
import sys
import os
import pytest
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
from robotlib.signal_manager import SignalManager
from robotlib.trading.order_types import OrderDirection, OrderType, OrderStatus
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from tests.mocks import MockOrderExecutor, MockAPIClient, MockPortfolioManager
# Убрали импорты базы данных - используем только моки
import pytz

logger = get_logger(__name__)

# Настраиваем уровень логирования для консоли
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@pytest.mark.asyncio
async def test_historical_trading(
    from_time: str = "2025-01-15 7:00",
    to_time: str = "2025-01-15 19:00"
):
    """
    Тестирует архитектуру OrderIntent → OrderExecution на исторических данных
    
    Поток выполнения:
    1. Создаем мокированные исторические свечи
    2. Инициализируем StrategyManager с OrderExecutor
    3. Обрабатываем каждую свечу через strategy_manager.on_candle()
    4. Стратегии создают OrderIntent на основе сигналов
    5. OrderExecutor выполняет ордера и возвращает OrderExecution
    6. Результаты передаются обратно в стратегии
    7. Собираем статистику по доходам и сделкам
    """
    logger.info("🚀 Запуск тестирования архитектуры OrderIntent → OrderExecution на исторических данных")
    
    # Загружаем конфигурацию
    config = load_config()
    token = config.tcs_client.token
    account_id = config.tcs_client.account_id
    sandbox_token = config.tcs_client.sandbox_token
    
    from_time_dt = _to_msk_date(from_time)
    to_time_dt = _to_msk_date(to_time)
    figi = "FUTIMOEXF000"
    
    # Создаем мокированные исторические данные
    logger.info(f"📊 Создаем мокированные исторические данные с {from_time} по {to_time}")
    historical_candles = _create_mock_candles(from_time_dt, to_time_dt)
    logger.info(f"✅ Создано {len(historical_candles)} мокированных свечей")
    
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
            strategies=strategies,
            order_executor=order_executor  # ✅ Передаем OrderExecutor
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


def _create_mock_candles(from_time: datetime, to_time: datetime):
    """Создает мокированные исторические свечи для тестирования"""
    import random
    from datetime import timedelta
    
    candles = []
    current_time = from_time
    base_price = 1500.0  # Базовая цена фьючерса
    
    while current_time < to_time:
        # Создаем свечу с реалистичными данными
        class MockCandle:
            def __init__(self, time, open_price, high_price, low_price, close_price, volume):
                self.time = time
                self.open = open_price
                self.high = high_price
                self.low = low_price
                self.close = close_price
                self.volume = volume
        
        # Генерируем случайные изменения цены
        price_change = random.uniform(-0.02, 0.02)  # ±2% изменение
        open_price = base_price
        close_price = open_price * (1 + price_change)
        
        # Создаем high и low на основе open и close
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.01))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.01))
        
        # Генерируем объем
        volume = random.randint(100, 1000)
        
        candle = MockCandle(
            time=current_time,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=volume
        )
        
        candles.append(candle)
        
        # Обновляем базовую цену для следующей свечи
        base_price = close_price
        
        # Переходим к следующей минуте
        current_time += timedelta(minutes=1)
    
    return candles


async def main():
    """Главная функция для запуска тестирования"""
    logger.info("🎯 Тестирование архитектуры OrderIntent → OrderExecution")
    
    # Тест с мокированными данными
    try:
        logger.info("🧪 Тест: С мокированными историческими данными")
        result = await test_historical_trading(
            from_time="2025-01-15 7:00",
            to_time="2025-01-15 19:00"
        )
        logger.info(f"✅ Тест завершен: {result}")
    except Exception as e:
        logger.error(f"❌ Тест не удался: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
