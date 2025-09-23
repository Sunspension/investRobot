# Руководство по тестированию на исторических данных

## Обзор

Это руководство показывает, как тестировать новую архитектуру `OrderIntent` → `OrderExecution` на исторических данных с использованием двух источников данных.

## Архитектура тестирования

### OrderIntent → OrderExecution Flow
1. **Стратегии создают `OrderIntent`** (намерение на сделку)
2. **`StrategyManager` получает `OrderIntent`** от стратегий
3. **`OrderExecutor.execute_order()`** выполняет ордер
4. **Создается `OrderExecution`** с результатами исполнения
5. **`StrategyManager` передает `OrderExecution`** в стратегии
6. **Стратегии обрабатывают результат** через `_process_execution()`

## Источники данных

### 1. База данных SQLite
- **Назначение**: Тестирование на сохраненных исторических данных
- **Преимущества**: Быстро, реалистичные данные, не требует API
- **Требования**: Предварительно загруженные данные в `data/market.db`

### 2. Реальный Tinkoff API
- **Назначение**: Тестирование на актуальных данных
- **Преимущества**: Актуальные данные, полная реалистичность
- **Требования**: Валидные токены Tinkoff API

## Примеры использования

### Базовое тестирование с базой данных

```python
import asyncio
from datetime import datetime
from robotlib.utils.logger import get_logger
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy
from robotlib.signal_manager import SignalManager
from robotlib.trading.risk_manager import RiskManager, RiskLimits
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.utils.sql_repository import iter_candles
from robotlib.utils.sql_schema import init_db
from tests.trading_mocks import MockOrderExecutor, MockAPIClient, MockPortfolioManager
import pytz

logger = get_logger(__name__)

async def test_with_database(
    from_time: str = "2024-12-02 7:00",
    to_time: str = "2024-12-02 19:00",
    db_path: str = "data/market.db"
):
    """Тестирование с данными из базы SQLite"""
    
    # Загружаем исторические данные
    logger.info(f"📊 Загружаем данные с {from_time} по {to_time}")
    
    await init_db(db_path)
    from_time_dt = _to_msk_date(from_time)
    to_time_dt = _to_msk_date(to_time)
    figi = "FUTIMOEXF000"
    
    db_candles = [candle async for candle in iter_candles(db_path, figi, from_time_dt, to_time_dt)]
    
    # Конвертируем DBCandle в совместимый формат
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
    
    logger.info(f"✅ Загружено {len(historical_candles)} свечей")
    
    # Создаем компоненты системы
    async with MockAPIClient(deposit=400000) as mock_api_client:
        portfolio_manager = MockPortfolioManager(mock_api_client)
        
        order_executor = MockOrderExecutor(
            success_rate=1.0,
            commission_rate=0.01,
            mock_prices={figi: 1500.0}
        )
        
        risk_limits = RiskLimits(
            max_daily_loss=40000,
            max_position_size=200000,
            percent_from_deposit=50,
            items_per_trade=20,
            stop_loss_threshold=5.0
        )
        
        # Создаем менеджеры
        signal_manager = SignalManager()
        risk_manager = RiskManager(risk_limits)
        
        strategies = [
            LongStrategy(risk_manager, portfolio_manager),
            ShortStrategy(risk_manager, portfolio_manager)
        ]
        
        strategy_manager = StrategyManager(
            signal_manager=signal_manager,
            risk_manager=risk_manager,
            portfolio_manager=portfolio_manager,
            order_executor=order_executor,
            strategies=strategies
        )
        
        # Инициализируем стратегии
        await strategy_manager.initialize(figi, point_value=1.0, contracts_per_lot=10)
        
        # Обрабатываем свечи
        for i, candle in enumerate(historical_candles):
            await strategy_manager.on_candle(candle)
            
            if i % 100 == 0:
                logger.info(f"📈 Обработано {i+1}/{len(historical_candles)} свечей")
        
        # Закрываем позиции
        await strategy_manager.close_all_positions()
        
        # Возвращаем результаты
        return {
            'income': strategy_manager.income,
            'trades_count': len(strategy_manager.trades),
            'candles_count': len(historical_candles),
            'executions_count': len(order_executor._executions),
            'long_income': strategies[0].income,
            'short_income': strategies[1].income
        }

def _to_msk_date(date: str, tz_info=False) -> datetime:
    """Конвертирует строку даты в московское время"""
    dt_naive = datetime.strptime(date, "%Y-%m-%d %H:%M")
    moscow_tz = pytz.timezone("Europe/Moscow")
    dt_moscow = moscow_tz.localize(dt_naive)
    return dt_moscow if tz_info else dt_moscow.replace(tzinfo=None)

# Запуск теста
if __name__ == '__main__':
    result = asyncio.run(test_with_database())
    logger.info(f"Результат тестирования: {result}")
```

### Тестирование с реальным API

```python
from config_data.config import load_config
from tinkoff.invest.exceptions import InvestError
from tinkoff.invest import CandleInterval
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient

async def test_with_api(
    from_time: str = "2025-01-15 7:00",
    to_time: str = "2025-01-15 19:00"
):
    """Тестирование с данными из Tinkoff API"""
    
    # Загружаем конфигурацию
    config = load_config()
    token = config.tcs_client.token
    account_id = config.tcs_client.account_id
    sandbox_token = config.tcs_client.sandbox_token
    
    from_time_dt = _to_msk_date(from_time)
    to_time_dt = _to_msk_date(to_time)
    figi = "FUTIMOEXF000"
    
    # Загружаем данные через API
    logger.info("🌐 Загружаем данные через Tinkoff API...")
    async with TinkoffAPIClient(token, account_id, sandbox_token) as api_client:
        historical_candles = [item async for item in _load_historic_data(api_client, figi, from_time_dt, to_time_dt)]
    
    logger.info(f"✅ Загружено {len(historical_candles)} свечей через API")
    
    # Остальная логика аналогична test_with_database()
    # ... (создание компонентов, обработка свечей, возврат результатов)

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
```

## Загрузка данных в базу

Для использования базы данных нужно предварительно загрузить данные:

```python
from robotlib.utils.candles_loader import load_month_candles_to_db
from datetime import datetime

# Загружаем данные за месяц
saved_count = await load_month_candles_to_db(
    app_name="trading_bot",
    account_id="your_account_id",
    token="your_token",
    sandbox_token="your_sandbox_token",
    db_path="data/market.db",
    figi="FUTIMOEXF000",
    start_date_inclusive=datetime(2024, 12, 1)
)

logger.info(f"Загружено {saved_count} свечей в базу данных")
```

## Результаты тестирования

Система возвращает детальную статистику:

```python
{
    'income': 577800.0,           # Общий доход
    'trades_count': 0,            # Количество сделок
    'candles_count': 705,         # Количество обработанных свечей
    'executions_count': 146,      # Количество исполненных ордеров
    'long_income': 588300.0,      # Доход от Long стратегии
    'short_income': -10500.0      # Доход от Short стратегии
}
```

## Преимущества архитектуры

1. **Гибкость** - поддержка разных источников данных
2. **Реалистичность** - тестирование на реальных исторических данных
3. **Детальность** - полная статистика по исполненным ордерам
4. **Совместимость** - работает с существующей архитектурой
5. **Тестируемость** - легко создавать unit-тесты с моками

## Ограничения

1. **База данных** - требует предварительной загрузки данных
2. **API** - требует валидные токены Tinkoff
3. **Время** - загрузка через API может быть медленной
4. **Зависимости** - требует настройки базы данных

---

*Это руководство показывает, как правильно тестировать торговые стратегии на исторических данных, следуя принципам проекта и используя реальные данные вместо мок-данных.*
