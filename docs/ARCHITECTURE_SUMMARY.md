# Краткая сводка архитектуры investRobot

## 🎯 Назначение системы

**investRobot** - автоматическая торговая система для фьючерсов на основе технических индикаторов MACD с использованием Tinkoff Invest API.

## 🏗️ Архитектурные принципы

- **Event-Driven Architecture** - обмен данными через события
- **Dependency Injection** - инверсия зависимостей через DI контейнер
- **SOLID принципы** - чистая архитектура
- **Асинхронность** - неблокирующие операции
- **Тестируемость** - все компоненты через интерфейсы

## 📦 Основные компоненты

### 1. **TradingSystemContainer** (DI Container)
- Создание и управление всеми зависимостями
- Singleton pattern для компонентов
- Ленивая инициализация

### 2. **EventBus** (Шина событий)
- Центральная шина для обмена событиями
- Типы: CANDLE_RECEIVED, SIGNAL_GENERATED, ORDER_PLACED, etc.
- Асинхронная обработка

### 3. **SignalManager** (Менеджер сигналов)
- Генерация сигналов на основе MACD
- Обнаружение пиков и впадин
- Адаптивное окно анализа

### 4. **PortfolioManager** (Менеджер портфеля)
- Управление портфелем и позициями
- Кэширование данных
- Публикация событий обновления

### 5. **SessionController** (Контроллер сессии)
- Управление жизненным циклом
- Проверка статуса рынка
- Обработка ошибок

### 6. **StrategyManager** (Менеджер стратегий)
- Управление торговыми стратегиями
- Long/Short стратегии
- Выполнение сигналов

### 7. **OrderExecutor** (Исполнитель ордеров)
- Выполнение торговых ордеров
- Поддержка Market/Limit ордеров
- Обработка результатов

### 8. **MarketDataStream** (Поток данных)
- Получение и кэширование свечей
- Публикация событий о новых данных
- Ограничение размера кэша

### 9. **RiskManager** (Менеджер рисков)
- Управление торговыми рисками
- Проверка лимитов
- Генерация отчетов

### 10. **DashEventVisualizer** (Визуализатор)
- Веб-интерфейс для мониторинга
- Реальное время отображения
- Графики и статистика

## 🔄 Потоки данных

### Основной торговый поток:
```
MarketDataStream → EventBus → SignalManager → StrategyManager → OrderExecutor → PortfolioManager
```

### Поток визуализации:
```
EventBus → DashEventVisualizer → DataManager → UIComponents → Dash App
```

## 🚀 Запуск системы

```python
# Простой запуск
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig

async def main():
    config = TradingConfig(figi="FUTIMOEXF000", enable_visualization=True)
    container = TradingSystemContainer(config, enable_visualization=True)
    trading_system = await container.build_trading_system()
    
    session_controller = trading_system['session_controller']
    await session_controller.start()

asyncio.run(main())
```

## 📁 Структура проекта

```
robotlib/
├── trading/           # Торговые компоненты
│   ├── di_container.py        # DI контейнер
│   ├── event_bus_interface.py # Шина событий
│   ├── interfaces.py          # Интерфейсы
│   ├── session_controller.py  # Контроллер сессии
│   ├── portfolio_manager.py   # Менеджер портфеля
│   ├── order_executor.py      # Исполнитель ордеров
│   ├── market_data_stream.py  # Поток данных
│   └── risk_manager.py        # Менеджер рисков
├── strategies/        # Торговые стратегии
│   ├── strategy_manager.py    # Менеджер стратегий
│   ├── long.py               # Long стратегия
│   └── short.py              # Short стратегия
├── signal_manager.py  # Менеджер сигналов
└── utils/            # Утилиты
    ├── logger.py             # Логирование
    ├── money.py              # Работа с деньгами
    └── market_hours_enhanced.py # Часы торгов

visualization/        # Визуализация
├── dash_event_visualizer.py  # Dash визуализатор
├── data_manager.py           # Менеджер данных
├── chart_builder.py          # Построение графиков
└── ui_components.py          # UI компоненты

tests/               # Тесты
├── test_di_container.py      # Тесты DI
├── test_signal_manager.py    # Тесты сигналов
├── test_portfolio_manager.py # Тесты портфеля
└── mocks/                    # Моки для тестов
```

## 🧪 Тестирование

- **345 тестов** - полное покрытие
- **Моки для всех зависимостей** - изоляция тестов
- **Асинхронные тесты** - pytest-asyncio
- **Интеграционные тесты** - проверка взаимодействий

## 📊 Мониторинг

- **Логирование** - все операции логируются
- **Визуализация** - веб-интерфейс в реальном времени
- **Статистика** - метрики торговли
- **Обработка ошибок** - graceful degradation

## 🔧 Конфигурация

```python
TradingConfig(
    figi="FUTIMOEXF000",           # Инструмент
    auto_close_positions=True,     # Автозакрытие
    end_of_day_close=True,         # Закрытие в конце дня
    close_time=time(23, 50),       # Время закрытия
    warning_periods=[600, 300, 60], # Предупреждения
    enable_visualization=True      # Визуализация
)
```

## 📈 Производительность

- **Кэширование** - портфель, свечи, статус рынка
- **Асинхронность** - неблокирующие операции
- **Ограничение памяти** - ограничение размеров кэшей
- **Ленивая инициализация** - компоненты по требованию

## 🔒 Безопасность

- **Токены API** - в конфигурации
- **Валидация данных** - проверка входных данных
- **Обработка ошибок** - не раскрытие чувствительной информации
- **Логирование** - без чувствительных данных

## 🎯 Ключевые особенности

1. **Event-Driven** - все компоненты связаны через события
2. **Dependency Injection** - чистая архитектура
3. **Интерфейсы** - все компоненты тестируемы
4. **Асинхронность** - высокая производительность
5. **Визуализация** - мониторинг в реальном времени
6. **Тестируемость** - 345 тестов
7. **Расширяемость** - легко добавлять новые компоненты

## 📚 Документация

- **COMPLETE_ARCHITECTURE_SPECIFICATION.md** - полная спецификация
- **STRICT_RULES.md** - правила разработки
- **Примеры кода** - детальные примеры использования
- **Диаграммы** - визуальное представление архитектуры

---

**Система готова к продакшн использованию и может быть легко расширена новыми функциями и стратегиями.**
