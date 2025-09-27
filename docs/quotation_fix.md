# 🔧 Исправление ошибки Quotation в PositionSyncService

## ❌ **Проблема:**
```
2025-09-26 23:19:11 - investRobot.robotlib.trading.position_sync_service - WARNING - ⚠️ Попытка 1/3 не удалась: Error binding parameter 2: type 'Quotation' is not supported
```

## 🔍 **Причина:**
В `PositionSyncService` при создании `FIFOEntry` объекты `Quotation` передавались напрямую в поле `price`, но SQLite не поддерживает этот тип данных.

## ✅ **Решение:**
Добавлена конвертация `Quotation` в `float` перед созданием `FIFOEntry`:

```python
# Конвертируем price в float, если это Quotation
if hasattr(price, 'units') and hasattr(price, 'nano'):
    price_float = price.units + price.nano / 1_000_000_000
else:
    price_float = float(price)

fifo_entry = FIFOEntry(
    quantity=quantity,
    price=price_float,  # Теперь всегда float
    timestamp=datetime.fromisoformat(timestamp),
    order_id=order_id,
    direction=direction or "buy"
)
```

## 📍 **Исправленные места:**
1. **`_save_positions_from_api()`** - строка 134 (конвертация `position.avg_price`)
2. **`_restore_fifo_from_orders()`** - строка 172 (конвертация `price` из ордеров)
3. **`get_fifo_cache()`** - строка 296 (конвертация `price` из БД)

## 🎯 **Результат:**
- ✅ Ошибка `Quotation is not supported` исправлена
- ✅ Все 583 теста проходят
- ✅ `PositionSyncService` корректно работает с `Quotation` объектами
- ✅ Данные сохраняются в БД как `float` значения
