# Real-time архитектура визуализации

Текущая реализация использует прямой sink-интерфейс `VisualizationSinkable.on_*` для передачии событий в UI.

### 2. Типы событий

- `CANDLE_RECEIVED` - получена новая свеча
- `SIGNAL_GENERATED` - сгенерирован торговый сигнал
- `ORDER_PLACED` - размещен ордер
- `ORDER_FILLED` - исполнен ордер
- `POSITION_OPENED` - открыта позиция
- `POSITION_CLOSED` - закрыта позиция
- `PORTFOLIO_UPDATED` - обновлен портфель
- `MARKET_STATUS_CHANGED` - изменился статус рынка

### 3. Dependency Injection Container

`TradingSystemContainer` управляет созданием и инжекцией всех зависимостей:

```python
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig

# Создание конфигурации
config = TradingConfig(
    figi="FUTIMOEXF000",
    enable_visualization=True
)

# Создание контейнера
container = TradingSystemContainer(config, enable_visualization=True)
trading_system = container.build_trading_system()

# Получение компонентов
session_controller = trading_system['session_controller']
visualizer = trading_system['visualizer']
```

## Интеграция компонентов

### PortfolioManager

Публикует события `PORTFOLIO_UPDATED` при обновлении портфеля:

```python
# В PortfolioManager визуализатор обновляется отдельно через API визуализатора
```

### OrderExecutor

Публикует события `ORDER_PLACED` и `ORDER_FILLED`:

```python
# Событие размещения ордера
placed_event = TradingEvent(
    EventType.ORDER_PLACED,
    {
        'order_id': order_id,
        'order_intent': order_intent,
        'execution': execution
    }
)
await visualizer.on_order(placed_event)

# Событие исполнения ордера
if result.success:
    filled_event = TradingEvent(
        EventType.ORDER_FILLED,
        {
            'order_id': order_id,
            'execution': execution,
            'executed_price': result.executed_price
        }
    )
    await visualizer.on_order(filled_event)
```

### StrategyManager

Публикует события `SIGNAL_GENERATED`:

```python
# В StrategyManager визуализатор уведомляется через sink
```

## Визуализация

### EventVisualizerable

Интерфейс для визуализаторов событий:

```python
class EventVisualizerable(ABC):
    async def start(self) -> None
    async def stop(self) -> None
    def is_running(self) -> bool
    async def handle_candle_event(self, event: TradingEvent) -> None
    async def handle_signal_event(self, event: TradingEvent) -> None
    # ... другие обработчики событий
```

### DashEventVisualizer

Реализация визуализатора для Dash:

```python
visualizer = DashEventVisualizer(figи="FUTIMOEXF000")

await visualizer.start()  # Запуск визуализатора
await visualizer.stop()   # Остановка визуализатора
```

## Использование

### Запуск системы

```bash
# С визуализацией
python run_trading_system.py

# Без визуализации
python run_trading_system.py --no-visualization

# С другим инструментом
python run_trading_system.py --figi "FUTSBERF000"
```

### Программный запуск

```python
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig

async def main():
    config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
    container = TradingSystemContainer(config, enable_visualization=True)
    trading_system = container.build_trading_system()
    
    # Запуск визуализатора
    if trading_system['visualizer']:
        await trading_system['visualizer'].start()
    
    # Запуск торговой сессии
    await trading_system['session_controller'].start()

asyncio.run(main())
```

## Преимущества

1. **Гибкость** - легко добавлять новые компоненты
2. **Тестируемость** - все компоненты легко мокаются
3. **Расширяемость** - простое добавление новых типов событий
4. **Независимость** - компоненты слабо связаны
5. **Переиспользование** - компоненты можно использовать в разных контекстах

## Тестирование

```python
# Тест с мок-визуализатором
container = TradingSystemContainer(config, enable_visualization=False)
trading_system = container.build_trading_system()

# Тест прямого вызова sink
await visualizer.on_candle({'price': 100.0})
```

