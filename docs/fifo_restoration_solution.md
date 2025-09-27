# Решение проблемы восстановления FIFO для позиций

## 🚨 **Проблема:**

### **Что происходит при восстановлении позиций:**
1. **API возвращает позицию**: `FUTIMOEXF000: 5 шт.`
2. **`_restore_fifo_from_orders()`** ищет таблицу `orders` - **НЕ НАХОДИТ**
3. **FIFO очередь остается пустой** - нет данных о последовательности
4. **`get_loss_positions()`** не может работать - нет FIFO данных
5. **Стратегии не могут** использовать FIFO логику для закрытия убыточных позиций

### **Последствия:**
- ❌ **Стратегии не могут** определить, какие позиции убыточные
- ❌ **FIFO логика не работает** - нет данных о последовательности покупок
- ❌ **Система не может** закрывать убыточные позиции по FIFO

## ✅ **Решение:**

### **Добавлен метод `_restore_fifo_from_api_if_needed()`:**

#### **1. Проверка существования FIFO данных:**
```python
# Проверяем, есть ли уже FIFO данные для этого FIGI
if figi in self._fifo_entries and self._fifo_entries[figi]:
    self._logger.debug(f"FIFO для {figi} уже существует, пропускаем")
    continue
```

#### **2. Запрос истории ордеров из API:**
```python
# Запрашиваем историю ордеров за последние 30 дней
from_date = datetime.now() - timedelta(days=30)
to_date = datetime.now()

operations = await self._api_client.get_operations_history(from_date, to_date)
```

#### **3. Фильтрация релевантных операций:**
```python
# Фильтруем операции по FIGI и статусу
relevant_operations = [
    op for op in operations 
    if hasattr(op, 'figi') and op.figi == figi and 
       hasattr(op, 'status') and op.status == 'filled'
]
```

#### **4. Создание FIFO записей:**
```python
# Создаем FIFO записи из операций
for op in relevant_operations:
    direction = OrderDirection.BUY if op.quantity > 0 else OrderDirection.SELL
    
    fifo_entry = FIFOEntry(
        figi=figi,
        direction=direction,
        quantity=abs(op.quantity),
        price=op.price,
        timestamp=op.time,
        order_id=op.order_id or f"api_{uuid.uuid4()}"
    )
    
    fifo_entries.append(fifo_entry)
```

#### **5. Сохранение FIFO данных:**
```python
# Добавляем FIFO записи
if fifo_entries:
    self._fifo_entries[figi] = fifo_entries
    self._logger.info(f"✅ Восстановлено {len(fifo_entries)} FIFO записей для {figi}")
```

### **Интеграция в процесс синхронизации:**

```python
async def sync_on_startup(self, max_retries: int = 3):
    # ... получение позиций из API ...
    
    # Восстанавливаем FIFO из истории ордеров
    await self._restore_fifo_from_orders()
    
    # Если FIFO пустой, пытаемся восстановить из API
    await self._restore_fifo_from_api_if_needed(api_positions)
    
    # ... остальная логика ...
```

## 🎯 **Результат:**

### **Теперь система может:**

#### **1. Восстанавливать FIFO из API:**
```
🔄 Восстановление FIFO для FUTIMOEXF000 из API истории ордеров...
✅ Восстановлено 3 FIFO записей для FUTIMOEXF000
```

#### **2. Использовать FIFO логику:**
```python
# Стратегии могут использовать FIFO
loss_positions = await position_manager.get_loss_positions(
    figi="FUTIMOEXF000",
    current_price=2700.0,
    loss_threshold=100.0
)
```

#### **3. Закрывать убыточные позиции:**
```python
# Получаем убыточные позиции по FIFO
for loss_pos in loss_positions:
    if loss_pos.loss_amount > loss_threshold:
        # Закрываем позицию
        await strategy.close_position(loss_pos)
```

## 📊 **Логи процесса:**

### **Успешное восстановление:**
```
🔄 Синхронизация позиций при старте...
Конвертировано 1 позиций из портфеля
🔄 Восстановление FIFO данных из истории ордеров...
📋 Таблица orders не найдена, пропускаем восстановление FIFO
🔄 Восстановление FIFO для FUTIMOEXF000 из API истории ордеров...
✅ Восстановлено 3 FIFO записей для FUTIMOEXF000
✅ Синхронизация завершена: 1 позиций
```

### **Проблемы с восстановлением:**
```
🔄 Восстановление FIFO для FUTIMOEXF000 из API истории ордеров...
⚠️ API не вернул историю операций для FUTIMOEXF000
⚠️ Нет заполненных операций для FUTIMOEXF000 в истории API
```

## 🔧 **Настройки:**

### **Период истории операций:**
```python
# Запрашиваем историю за последние 30 дней
from_date = datetime.now() - timedelta(days=30)
to_date = datetime.now()
```

### **Фильтрация операций:**
```python
# Только заполненные операции
if hasattr(op, 'status') and op.status == 'filled'
```

### **Обработка ошибок:**
```python
try:
    # Восстановление FIFO
    operations = await self._api_client.get_operations_history(...)
except Exception as e:
    self._logger.error(f"Ошибка восстановления FIFO для {figi} из API: {e}")
    continue
```

## 🎯 **Преимущества решения:**

1. **✅ Полная функциональность** - FIFO логика работает даже после восстановления
2. **✅ Автоматическое восстановление** - система сама восстанавливает FIFO из API
3. **✅ Отказоустойчивость** - работает даже при отсутствии локальной истории
4. **✅ Гибкость** - можно настроить период истории и фильтрацию
5. **✅ Логирование** - подробные логи для мониторинга процесса

---

*Решение реализовано: 2025-01-27*
