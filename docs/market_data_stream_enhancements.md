# Улучшения MarketDataStream

## Обзор

Модуль `MarketDataStream` был расширен для полной интеграции с Session Manager. Добавлено кэширование данных и новые методы для получения рыночных данных.

## Новые возможности

### 1. Кэширование свечей
- Автоматическое кэширование последних N свечей
- Настраиваемый размер кэша (по умолчанию 100 свечей)
- Автоматическое обновление текущей цены

### 2. Новые методы

#### `get_latest_candles(count: int = 10) -> List[Candle]`
Возвращает последние N свечей из кэша.

```python
# Получить последние 5 свечей
candles = await market_data_stream.get_latest_candles(5)
```

#### `get_current_price() -> Optional[float]`
Возвращает текущую цену инструмента.

```python
# Получить текущую цену
price = await market_data_stream.get_current_price()
```

#### `get_cached_candles() -> List[Candle]`
Возвращает все кэшированные свечи.

```python
# Получить все кэшированные свечи
all_candles = market_data_stream.get_cached_candles()
```

#### `get_cache_size() -> int`
Возвращает количество свечей в кэше.

```python
# Получить размер кэша
size = market_data_stream.get_cache_size()
```

#### `clear_cache() -> None`
Очищает кэш свечей.

```python
# Очистить кэш
market_data_stream.clear_cache()
```

## Интеграция с Session Manager

Теперь `SessionController` может получать данные через `MarketDataStream`:

```python
# В SessionController._get_new_candles()
candles = await self.dependencies.market_data_stream.get_latest_candles()
```

## Обновленный интерфейс

Интерфейс `MarketDataStreamable` расширен новыми методами:

```python
class MarketDataStreamable(Protocol):
    async def get_latest_candles(self, count: int = 10) -> List[Candle]:
        """Возвращает последние N свечей"""
        pass
    
    async def get_current_price(self) -> Optional[float]:
        """Возвращает текущую цену"""
        pass
    
    def get_cached_candles(self) -> List[Candle]:
        """Возвращает все кэшированные свечи"""
        pass
    
    def get_cache_size(self) -> int:
        """Возвращает размер кэша"""
        pass
    
    def clear_cache(self) -> None:
        """Очищает кэш свечей"""
        pass
```

## Использование

```python
# Инициализация
market_data_stream = MarketDataStream(
    api_client=api_client,
    signal_manager=signal_manager,
    figi="FUTIMOEXF000",
    cache_size=100
)

# Получение данных
candles = await market_data_stream.get_latest_candles(10)
current_price = await market_data_stream.get_current_price()
```
