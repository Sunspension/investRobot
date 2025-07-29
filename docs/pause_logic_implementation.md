# Логика паузы торговли

## Реализована логика паузы вместо остановки

### Было (остановка):
```python
except Exception as e:
    self.logger.error(f"Ошибка: {e}")
    raise Exception("Торговля невозможна без API")
    # ↑ СИСТЕМА ОСТАНАВЛИВАЕТСЯ НАВСЕГДА
```

### Стало (пауза):
```python
except Exception as e:
    self.logger.error(f"Ошибка: {e}")
    self.logger.info("Пауза торговли до восстановления API...")
    
    # Ждем восстановления API
    await self._wait_for_api_recovery()
    # ↑ СИСТЕМА ПАУЗИТСЯ И ЖДЕТ ВОССТАНОВЛЕНИЯ
```

## Новые методы

### 1. `_wait_for_api_recovery()`
```python
async def _wait_for_api_recovery(self) -> None:
    """Ждет восстановления API"""
    self.logger.info("Ожидание восстановления API...")
    
    while True:
        try:
            # Проверяем доступность API
            market_status = await get_market_status_with_api(self.dependencies.api_client)
            self.logger.info("API восстановлен!")
            break
            
        except Exception as e:
            self.logger.warning(f"API все еще недоступен: {e}")
            self.logger.info("Продолжаем ожидание...")
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд
```

### 2. Обновленный торговый цикл
```python
while self._is_running:
    try:
        # Обычная торговля
        candles = await self._get_new_candles()
        await self._process_candles(candles)
        
    except Exception as e:
        self.logger.error(f"Ошибка в торговом цикле: {e}")
        self.logger.info("Пауза торговли до восстановления...")
        
        # Ждем восстановления
        await self._wait_for_api_recovery()
        self.logger.info("Торговля возобновлена")
```

## Причины паузы торговли

- **Клиринг** - обработка сделок между сессиями
- **Технические работы** - обновление систем биржи
- **Недоступность API** - проблемы с интернетом
- **Ошибки API** - временные сбои Tinkoff

## Логика работы

1. **Обнаружение проблемы**: Ошибка API → Логирование → Пауза торговли
2. **Ожидание восстановления**: Проверка каждые 30 сек → API недоступен → Продолжаем ждать
3. **Восстановление**: API доступен → Логирование → Возобновление торговли
