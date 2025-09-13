# Event-Driven Architecture

## Обзор

Торговая система использует Event-Driven архитектуру с Dependency Injection для обеспечения гибкости, расширяемости и тестируемости.

## Основные компоненты

### 1. EventBus (Шина событий)

Центральный компонент для обмена событиями между модулями:

```python
from robotlib.trading.event_bus_interface import EventBus, EventType, TradingEvent

# Создание шины событий
event_bus = EventBus()

# Подписка на события
event_bus.subscribe(EventType.CANDLE_RECEIVED, handle_candle)

# Публикация событий
event = TradingEvent(EventType.CANDLE_RECEIVED, {'price': 100.0})
await event_bus.publish(event)
```

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
event_bus = trading_system['event_bus']
session_controller = trading_system['session_controller']
visualizer = trading_system['visualizer']
```

## Интеграция компонентов

### PortfolioManager

Публикует события `PORTFOLIO_UPDATED` при обновлении портфеля:

```python
# В PortfolioManager
if self._event_bus:
    event = TradingEvent(
        EventType.PORTFOLIO_UPDATED,
        {
            'portfolio': portfolio,
            'total_amount': total_amount,
            'available_amount': available_amount,
            'positions_count': len(positions)
        }
    )
    asyncio.create_task(self._event_bus.publish(event))
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
await event_bus.publish(placed_event)

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
    await event_bus.publish(filled_event)
```

### StrategyManager

Публикует события `SIGNAL_GENERATED`:

```python
# В StrategyManager
if self._event_bus:
    signal_event = TradingEvent(
        EventType.SIGNAL_GENERATED,
        {
            'signal': signal,
            'candle': candle,
            'figi': getattr(candle, 'figi', 'unknown')
        }
    )
    asyncio.create_task(self._event_bus.publish(signal_event))
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
visualizer = DashEventVisualizer(
    event_bus=event_bus,
    figi="FUTIMOEXF000"
)

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

# Проверка типа EventBus
assert isinstance(trading_system['event_bus'], EventBusable)

# Тест публикации событий
event = TradingEvent(EventType.CANDLE_RECEIVED, {'price': 100.0})
await trading_system['event_bus'].publish(event)
```

