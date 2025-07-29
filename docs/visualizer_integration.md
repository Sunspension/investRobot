# Интеграция визуализатора с торговой системой

## Обзор

Визуализатор интегрирован с торговой системой через интерфейс `TradingVisualizerable` и может быть включен/отключен через конфигурацию.

## Компоненты

### 1. Интерфейс TradingVisualizerable

```python
class TradingVisualizerable(ABC):
    async def add_candle(self, candle_data: Dict[str, Any]) -> None
    async def add_signal(self, signal_data: Dict[str, Any]) -> None
    async def add_order(self, order_data: Dict[str, Any]) -> None
    async def update_portfolio(self, portfolio_data: Dict[str, Any]) -> None
    async def update_market_status(self, status_data: Dict[str, Any]) -> None
    async def start(self) -> None
    async def stop(self) -> None
    def is_running(self) -> bool
```

### 2. Адаптер TradingVisualizerAdapter

Адаптер для существующего `TradingSignalsVisualizer`:

```python
visualizer = TradingVisualizerAdapter(
    figi="FUTIMOEXF000",
    host="127.0.0.1",
    port=8050
)
```

### 3. Фабрика TradingVisualizerFactory

```python
factory = TradingVisualizerFactory()
visualizer = factory.create_visualizer(config)
```

## Конфигурация

### TradingConfig

```python
config = TradingConfig(
    figi="FUTIMOEXF000",
    enable_visualization=True,  # Включить визуализацию
    auto_close_positions=True,
    end_of_day_close=True
)
```

## Использование

### 1. Создание визуализатора

```python
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.trading_config import TradingConfig

# Создаем конфигурацию
config = TradingConfig(
    figi="FUTIMOEXF000",
    enable_visualization=True
)

# Создаем фабрику
factory = TradingVisualizerFactory()

# Создаем визуализатор
visualizer = factory.create_visualizer(config)
```

### 2. Интеграция с SessionController

```python
from robotlib.trading.session_controller import SessionController

# Создаем контроллер с визуализатором
controller = SessionController(
    config=config,
    dependencies=dependencies,
    visualizer=visualizer
)

# Запускаем сессию
await controller.start()
```

### 3. Автоматическая передача данных

Визуализатор автоматически получает:

- **Свечи** - через `_get_new_candles()`
- **Сигналы** - через `_process_candles()`
- **Ордера** - через `add_order()`
- **Портфель** - через `update_portfolio()`
- **Статус рынка** - через `update_market_status()`

## Возможности визуализатора

### 1. График свечей
- Реальные данные с Tinkoff API
- Обновление в реальном времени
- Интерактивность (зум, панорамирование)

### 2. Торговые сигналы
- Отображение на графике
- История сигналов
- Детальная информация

### 3. Ордера
- Треугольники на графике
- Цветовая индикация
- Hover информация

### 4. Информация о портфеле
- Статус стратегий
- Доход по стратегиям
- Позиции

### 5. Статус рынка
- Торговые часы
- Следующая сессия
- Время до закрытия

## Тестирование

### Мок визуализатор

```python
from robotlib.trading.visualizer_interface import MockTradingVisualizer

visualizer = MockTradingVisualizer()
await visualizer.add_candle(candle_data)
await visualizer.add_signal(signal_data)
```

### Тесты

```bash
python -m pytest tests/test_visualizer_integration.py -v
```

## Примеры

### Полный пример

```python
import asyncio
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.session_controller import SessionController

async def main():
    # Конфигурация
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    
    # Создаем визуализатор
    factory = TradingVisualizerFactory()
    visualizer = factory.create_visualizer(config)
    
    # Создаем контроллер
    controller = SessionController(
        config=config,
        dependencies=dependencies,
        visualizer=visualizer
    )
    
    # Запускаем
    await controller.start()
    
    # Визуализатор доступен по адресу: http://127.0.0.1:8050

if __name__ == "__main__":
    asyncio.run(main())
```

## Архитектура

```
TradingConfig
    ↓ (enable_visualization=True)
TradingVisualizerFactory
    ↓
TradingVisualizerAdapter
    ↓
TradingSignalsVisualizer (веб-интерфейс)
    ↓
SessionController (автоматическая передача данных)
```

## Преимущества

1. **Опциональность** - можно легко отключить
2. **Модульность** - не влияет на торговую логику
3. **Автоматическая передача** - данные передаются автоматически
4. **Тестируемость** - есть мок для тестов
5. **Гибкость** - можно заменить на другой визуализатор
