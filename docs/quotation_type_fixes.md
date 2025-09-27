# Исправления типов для Quotation объектов

## Проблема

В коде были несоответствия между типами аннотаций и реальными типами данных:

- `OrderExecution.price` должен быть `float`, но создавался с `Quotation` объектами
- Это приводило к ошибкам `Error binding parameter 2: type 'Quotation' is not supported`
- Нарушался принцип единообразия типов

## Решение

### 1. Конвертация Quotation в OrderExecutor

**Правильный подход**: конвертировать `Quotation` в `float` при создании `OrderExecution`:

```python
# В OrderExecutor.execute_order():
# Конвертируем price в float, если это Quotation
executed_price = result.executed_price or 0.0
if hasattr(executed_price, 'units') and hasattr(executed_price, 'nano'):
    executed_price = executed_price.units + executed_price.nano / 1_000_000_000
else:
    executed_price = float(executed_price)

execution = OrderExecution(
    # ...
    price=executed_price,  # Теперь всегда float
    # ...
)
```

### 2. Чистые типы в PositionManager

Теперь `PositionManager` принимает только `float`:

```python
# PositionManager методы остались с чистыми типами:
async def add_to_fifo(self, figi: str, quantity: int, price: float, order_id: str):
async def update_position_after_trade(self, figi: str, quantity_delta: int, price: float):
```

### 3. Конвертация в PositionSyncService

В `PositionSyncService` конвертация остается, так как он работает с API данными:

```python
# Конвертируем price в float, если это Quotation
if hasattr(price, 'units') and hasattr(price, 'nano'):
    price_float = price.units + price.nano / 1_000_000_000
else:
    price_float = float(price)
```

### 4. Архитектурный принцип

**Правило**: Конвертация типов должна происходить на границах системы:
- ✅ **OrderExecutor** → конвертирует `Quotation` в `float` при создании `OrderExecution`
- ✅ **PositionSyncService** → конвертирует `Quotation` в `float` при работе с API
- ✅ **PositionManager** → принимает только `float`, не конвертирует

## Результат

- ✅ Ошибка `Error binding parameter 2: type 'Quotation' is not supported` исправлена
- ✅ Типы аннотаций соответствуют реальности
- ✅ Все тесты проходят (583 passed)
- ✅ Время выполнения улучшилось (2.88s)

## Принцип

**Всегда конвертируйте Quotation в float перед передачей в SQLite!**

```python
# Правильно:
if hasattr(price, 'units') and hasattr(price, 'nano'):
    price_float = price.units + price.nano / 1_000_000_000
else:
    price_float = float(price)

# Используйте price_float в SQL запросах
```
