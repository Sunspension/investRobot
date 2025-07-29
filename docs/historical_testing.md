# Тестирование на исторических данных

## Обзор

Система тестирования новой архитектуры `OrderIntent` → `OrderExecution` на исторических данных с поддержкой двух источников данных.

## Источники данных

### 1. База данных SQLite
- **Назначение**: Тестирование на сохраненных исторических данных
- **Использование**: `use_database=True, db_path="data/market.db"`
- **Преимущества**: Быстро, реалистичные данные, не требует API
- **Недостатки**: Нужно предварительно загрузить данные

### 2. Реальный Tinkoff API
- **Назначение**: Тестирование на актуальных данных
- **Использование**: `use_database=False`
- **Преимущества**: Актуальные данные, полная реалистичность
- **Недостатки**: Требует API токен, медленно

## Использование

### Базовое тестирование
```bash
python test_historical_with_new_architecture.py
```

### Программное использование
```python
# Тест из базы данных
result = await test_historical_data_with_new_architecture(
    from_time="2024-12-02 7:00",
    to_time="2024-12-02 19:00",
    use_database=True,
    db_path="data/market.db"
)

# Тест с реальным API
result = await test_historical_data_with_new_architecture(
    from_time="2025-01-15 7:00",
    to_time="2025-01-15 19:00",
    use_database=False
)
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
    db_path="data/candles.db",
    figi="FUTIMOEXF000",
    start_date_inclusive=datetime(2025, 1, 1)
)
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

## Архитектура

### OrderIntent → OrderExecution
1. **Стратегии создают `OrderIntent`** (намерение на сделку)
2. **`StrategyManager` получает `OrderIntent`** от стратегий
3. **`OrderExecutor.execute_order()`** выполняет ордер
4. **Создается `OrderExecution`** с результатами исполнения
5. **`StrategyManager` передает `OrderExecution`** в стратегии
6. **Стратегии обрабатывают результат** через `_process_execution()`

### Компоненты
- **`MockOrderExecutor`** - симулирует исполнение ордеров
- **`MockAPIClient`** - мок API клиент для тестирования
- **`MockPortfolioManager`** - мок менеджер портфеля
- **Конвертеры данных** - для работы с разными форматами свечей

## Преимущества

1. **Гибкость** - поддержка разных источников данных
2. **Реалистичность** - тестирование на реальных исторических данных
3. **Скорость** - быстрые тесты с мок данными
4. **Детальность** - полная статистика по исполненным ордерам
5. **Совместимость** - работает с существующей архитектурой

## Ограничения

1. **База данных** - требует предварительной загрузки данных
2. **API** - требует валидные токены Tinkoff
3. **Время** - загрузка через API может быть медленной
4. **Зависимости** - требует настройки базы данных
