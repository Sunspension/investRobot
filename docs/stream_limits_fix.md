# Исправление проблемы с лимитом стримов

## 🚨 **Проблема:**
```
Watchdog уже запущен
Watchdog уже запущен
None MarketDataStream CANCELLED Received RST_STREAM with error code 8
Ошибка/отмена стрима: (<StatusCode.CANCELLED: (1, 'cancelled')>, 'Received RST_STREAM with error code 8', Metadata(tracking_id=None, ratelimit_limit='600, 600;w=60', ratelimit_remaining=86, ratelimit_reset=4, message='Limit of open streams exceeded'))
```

## 🔍 **Причина:**
При перезапуске фонового процесса `run_candle_sink.py` старые стримы не закрываются корректно, что приводит к накоплению открытых соединений и превышению лимита Tinkoff API.

## ✅ **Исправления:**

### **1. Исправлен конструктор MarketDataStream:**
```python
# ❌ БЫЛО - старый конструктор
stream = MarketDataStream(
    api_client=api_client,
    figi=figi,
    watchdog_enabled=cfg.watchdog_enabled,
    # ...
)

# ✅ СТАЛО - новый конструктор с компонентами
candle_cache = CandleCache(cache_size=100)
historical_loader = HistoricalDataLoader(api_client, figi)
watchdog = StreamWatchdog(...) if cfg.watchdog_enabled else None

stream = MarketDataStream(
    api_client=api_client,
    figi=figi,
    candle_cache=candle_cache,
    historical_loader=historical_loader,
    watchdog=watchdog,
)
```

### **2. Исправлена ошибка с sink.close():**
```python
# ❌ БЫЛО - неопределенная переменная
await sink.close()

# ✅ СТАЛО - правильная переменная
await candle_sink.close()
```

### **3. Добавлена принудительная остановка стрима:**
```python
# При неудачном старте
if not ok:
    try:
        await stream.stop()
        await asyncio.sleep(2.0)  # Задержка для закрытия соединения
    except Exception as e:
        logger.warning(f"Ошибка остановки стрима: {e}")

# При падении стрима
if not stream.is_running:
    try:
        await stream.stop()
        await asyncio.sleep(2.0)  # Задержка для закрытия соединения
    except Exception as e:
        logger.warning(f"Ошибка остановки стрима при перезапуске: {e}")
```

### **4. Улучшена обработка ошибок в TinkoffStreamAdapter:**
```python
def stop(self) -> None:
    """Останавливает стрим (синхронный метод)"""
    try:
        self._stream_manager.stop()
        self._logger.debug("Стрим менеджер остановлен")
    except Exception as e:
        self._logger.warning(f"Ошибка остановки стрим менеджера: {e}")
```

## 🎯 **Результат:**

### ✅ **Корректное закрытие соединений:**
- **Принудительная остановка** стрима перед перезапуском
- **Задержка 2 секунды** для корректного закрытия соединения
- **Обработка ошибок** при остановке стрима

### ✅ **Предотвращение накопления соединений:**
- **Остановка перед повторной попыткой** при неудачном старте
- **Остановка при падении стрима** перед перезапуском
- **Корректная очистка ресурсов** в finally блоке

### ✅ **Улучшенное логирование:**
- **Детальные сообщения** о состоянии стрима
- **Предупреждения** об ошибках остановки
- **Отладочная информация** о процессе

## 🚀 **Использование:**

Теперь `run_candle_sink.py` корректно управляет стримами и не накапливает открытые соединения:

```bash
# Запуск фонового процесса сбора свечей
python run_candle_sink.py --figi FUTIMOEXF000 --db data/market.db

# Остановка через Ctrl+C или SIGTERM
# Процесс корректно закроет все соединения
```

## 📝 **Примечания:**

- **Задержка 2 секунды** может показаться большой, но она необходима для корректного закрытия gRPC соединений
- **Принудительная остановка** гарантирует, что старые стримы не остаются висеть
- **Обработка ошибок** предотвращает падение процесса при проблемах с API

---

*Исправления применены: 2025-01-27*
