# API-Only Trading Hours

## Изменения в системе торговых часов

### Удалено:
- Fallback система для торговых часов
- Статическое расписание как резерв
- Методы `_get_fallback_schedule()` и `_fallback_is_trading_time()`

### Новая логика:
- **Только API**: Система работает исключительно через Tinkoff API
- **Строгие ошибки**: При недоступности API система останавливается
- **Нет резерва**: Если нет API - нет торговли

## Измененные файлы

### 1. `robotlib/utils/market_hours.py`
```python
# БЫЛО:
async def get_market_status_with_api(dt: Optional[datetime] = None) -> dict:
    if HAS_API:
        try:
            return await get_market_status_api(dt)
        except Exception:
            pass
    
    # Fallback к статическому расписанию
    return MarketHours.get_trading_status(dt)

# СТАЛО:
async def get_market_status_with_api(dt: Optional[datetime] = None) -> dict:
    if not HAS_API:
        raise Exception("Tinkoff API недоступен. Торговля невозможна без API.")
    
    return await get_market_status_api(dt)
```

### 2. `robotlib/utils/tinkoff_market_hours.py`
```python
# БЫЛО:
except Exception as e:
    self.logger.error(f"Ошибка проверки торговых часов: {e}")
    return self._fallback_is_trading_time(dt)

# СТАЛО:
except Exception as e:
    self.logger.error(f"Ошибка проверки торговых часов: {e}")
    raise Exception(f"Не удалось получить торговые часы через API: {e}")
```

### 3. `robotlib/trading/session_controller.py`
```python
# БЫЛО:
except Exception as e:
    self.logger.error(f"Ошибка проверки статуса рынка: {e}")
    return False

# СТАЛО:
except Exception as e:
    self.logger.error(f"Ошибка проверки статуса рынка: {e}")
    self.logger.error("Торговля невозможна без доступа к API")
    raise Exception(f"Не удалось проверить статус рынка: {e}")
```

## Принцип работы

1. **Проверка API доступности**: `HAS_API` должен быть `True`
2. **Получение данных**: Только через `TinkoffMarketHours.get_trading_schedule()`
3. **Обработка ошибок**: При любой ошибке API - исключение
4. **Остановка торговли**: Без API торговля невозможна

## Использование

```python
# Проверка торговых часов
try:
    market_status = await get_market_status_with_api()
    if market_status['is_trading']:
        print("Рынок открыт")
    else:
        print("Рынок закрыт")
except Exception as e:
    print(f"Ошибка: {e}")
    # Торговля невозможна
```

Система теперь работает по принципу "API или ничего" - без актуальных данных о торговых часах торговать нельзя.
