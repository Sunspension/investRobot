# Руководство по торговле с визуализацией

## Обзор

Теперь торговая система поддерживает опциональную визуализацию в реальном времени. Визуализатор отображает график свечей, торговые сигналы, ордера и состояние портфеля.

## Быстрый старт

### 1. Запуск с визуализацией

```bash
python run_trading_with_visualization.py
```

### 2. Открытие веб-интерфейса

После запуска откройте в браузере: **http://127.0.0.1:8050**

## Конфигурация

### Включение/отключение визуализации

```python
from robotlib.trading.trading_config import TradingConfig

# С визуализацией
config = TradingConfig(
    figi="FUTIMOEXF000",
    enable_visualization=True  # Включаем визуализацию
)

# Без визуализации
config = TradingConfig(
    figi="FUTIMOEXF000",
    enable_visualization=False  # Отключаем визуализацию
)
```

## Возможности визуализатора

### 1. График свечей
- Реальные данные с Tinkoff API
- Обновление в реальном времени
- Интерактивность (зум, панорамирование)

### 2. Торговые сигналы
- Отображение на графике (треугольники)
- История сигналов
- Детальная информация (цена, время, причина)

### 3. Ордера
- Треугольники на графике
- Цветовая индикация (зеленый/красный)
- Hover информация

### 4. Информация о портфеле
- Статус стратегий
- Доход по стратегиям
- Позиции

### 5. Статус рынка
- Торговые часы
- Следующая сессия
- Время до закрытия

## Примеры использования

### Базовый пример

```python
import asyncio
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.session_controller import SessionController

async def main():
    # Конфигурация с визуализацией
    config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    
    # Создаем визуализатор
    factory = TradingVisualizerFactory()
    visualizer = factory.create_visualizer(config)
    
    # Создаем контроллер (зависимости нужно создать отдельно)
    controller = SessionController(
        config=config,
        dependencies=dependencies,
        visualizer=visualizer
    )
    
    # Запускаем
    await controller.start()
    await controller.run_trading_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

### Полный пример с зависимостями

```python
import asyncio
from config_data.config import load_config
from robotlib.trading.trading_config import TradingConfig
from robotlib.trading.visualizer_factory import TradingVisualizerFactory
from robotlib.trading.session_controller import SessionController
from robotlib.trading.interfaces import TradingDependencies
# ... импорты всех компонентов

async def main():
    # Загружаем конфигурацию
    config = load_config()
    
    # Создаем конфигурацию торговли
    trading_config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    
    # Создаем зависимости
    dependencies = await create_trading_dependencies(config)
    
    # Создаем визуализатор
    factory = TradingVisualizerFactory()
    visualizer = factory.create_visualizer(trading_config)
    
    # Создаем контроллер
    controller = SessionController(
        config=trading_config,
        dependencies=dependencies,
        visualizer=visualizer
    )
    
    # Запускаем
    await controller.start()
    await controller.run_trading_loop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Архитектура

```
TradingConfig (enable_visualization=True)
    ↓
TradingVisualizerFactory
    ↓
TradingVisualizerAdapter
    ↓
TradingSignalsVisualizer (веб-интерфейс)
    ↓
SessionController (автоматическая передача данных)
    ↓
TradingDependencies (реальная торговля)
```

## Автоматическая передача данных

Визуализатор автоматически получает:

1. **Свечи** - из `_get_new_candles()`
2. **Сигналы** - из `_process_candles()`
3. **Ордера** - через `add_order()`
4. **Портфель** - через `update_portfolio()`
5. **Статус рынка** - через `update_market_status()`

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

## Устранение неполадок

### Визуализатор не запускается

1. Проверьте, что `enable_visualization=True` в конфигурации
2. Проверьте, что порт 8050 свободен
3. Проверьте логи на ошибки

### Данные не отображаются

1. Проверьте, что торговая сессия запущена
2. Проверьте, что API клиент работает
3. Проверьте, что рынок открыт

### Ошибки импорта

1. Убедитесь, что все зависимости установлены
2. Проверьте, что путь к проекту правильный
3. Проверьте, что конфигурация загружается

## Производительность

- Визуализатор работает в отдельном потоке
- Не влияет на производительность торговли
- Можно отключить для продакшн торговли

## Безопасность

- Визуализатор работает только локально
- Не передает данные наружу
- Можно отключить для продакшн торговли

