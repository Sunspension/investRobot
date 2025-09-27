# Оптимизация стримов завершена - Этап 2

## ✅ **Выполнено:**

### **Проблема:**
```
MarketDataStream CANCELLED Received RST_STREAM with error code 8
Limit of open streams exceeded
```

**Два отдельных стрима для одного FIGI:**
1. **`run_candle_sink.py`** - запись свечей в базу
2. **`TradingSystemContainer.get_market_data_stream()`** - для торговой системы

### **Решение:**

#### **1. Создан StreamRegistry:**
```python
# robotlib/trading/stream_registry.py
class StreamRegistry:
    def register_stream(self, figi: str, stream: MarketDataStream, subscriber_id: str) -> MarketDataStream:
        """Регистрирует стрим или возвращает существующий"""
        
    def unregister_subscriber(self, figi: str, subscriber_id: str) -> bool:
        """Отписывает подписчика от стрима"""
        
    def get_stream(self, figi: str) -> Optional[MarketDataStream]:
        """Получает существующий стрим"""
```

#### **2. Обновлен TradingSystemContainer:**
```python
async def get_market_data_stream(self) -> MarketDataStream:
    registry = get_stream_registry()
    existing_stream = registry.get_stream(self._config.figi)
    
    if existing_stream:
        self._logger.info(f"Переиспользуем существующий стрим для {self._config.figi}")
        return existing_stream
    
    # Создаем новый стрим и регистрируем его
    new_stream = MarketDataStream(...)
    subscriber_id = f"trading_system_{id(self)}"
    return registry.register_stream(self._config.figi, new_stream, subscriber_id)
```

#### **3. Обновлен run_candle_sink.py:**
```python
async def _run_candle_sink(figi: str, db_path: str, run_seconds: Optional[int]) -> None:
    registry = get_stream_registry()
    existing_stream = registry.get_stream(figi)
    
    if existing_stream:
        logger.info(f"Переиспользуем существующий стрим для {figi}")
        stream = existing_stream
    else:
        # Создаем новый стрим и регистрируем его
        stream = MarketDataStream(...)
        subscriber_id = f"candle_sink_{id(stream)}"
        stream = registry.register_stream(figi, stream, subscriber_id)
```

## 🎯 **Результат:**

### **Архитектура:**

#### **До оптимизации:**
```
run_candle_sink.py ──┐
                     ├── MarketDataStream (FUTIMOEXF000) ──┐
TradingSystem ───────┘                                    ├── Tinkoff API
                                                          └── Limit exceeded!
```

#### **После оптимизации:**
```
run_candle_sink.py ──┐
                     ├── StreamRegistry ── MarketDataStream (FUTIMOEXF000) ── Tinkoff API
TradingSystem ───────┘
```

### **Преимущества:**

#### ✅ **Устранено дублирование:**
- **Один стрим на FIGI**: Несколько компонентов используют один стрим
- **Меньше соединений**: Снижена нагрузка на API
- **Нет превышения лимитов**: Устранена ошибка "Limit of open streams exceeded"

#### ✅ **Улучшена производительность:**
- **Переиспользование ресурсов**: Один стрим для нескольких подписчиков
- **Лучшее управление**: Централизованный реестр стримов
- **Автоматическая очистка**: Стримы закрываются, когда нет подписчиков

#### ✅ **Упрощена архитектура:**
- **Единая точка управления**: StreamRegistry контролирует все стримы
- **Прозрачность**: Компоненты не знают о переиспользовании
- **Масштабируемость**: Легко добавлять новых подписчиков

## 📊 **Тестирование:**

### **Автоматическое переиспользование:**
```python
# Первый компонент создает стрим
stream1 = registry.register_stream("FUTIMOEXF000", new_stream, "component1")

# Второй компонент получает существующий стрим
stream2 = registry.register_stream("FUTIMOEXF000", new_stream, "component2")
# stream2 == stream1 (тот же объект)
```

### **Управление подписчиками:**
```python
# Отписываемся от стрима
can_close = registry.unregister_subscriber("FUTIMOEXF000", "component1")

# Если подписчиков не осталось, стрим можно закрыть
if can_close:
    # Стрим будет удален из реестра
    pass
```

## 🚀 **Следующие шаги:**

### **Этап 3: SharedMarketDataStream**
1. **Спроектировать архитектуру** для более сложных сценариев
2. **Реализовать SharedMarketDataStream** с продвинутыми возможностями
3. **Мигрировать существующие компоненты** на новую архитектуру
4. **Протестировать и оптимизировать** производительность

## 📈 **Ожидаемые результаты:**

### **Количественные:**
- **Стримы**: 2 → 1 (для одного FIGI)
- **Соединения к API**: 2 → 1
- **Ошибки "Limit exceeded"**: 0

### **Качественные:**
- **Стабильность**: Меньше перезапусков стримов
- **Производительность**: Лучшее использование ресурсов
- **Масштабируемость**: Легко добавлять новых подписчиков

---

*Этап 2 выполнен: 2025-01-27*
