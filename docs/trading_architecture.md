# 🏗️ Архитектура торговой системы

## 📊 Общая схема

```
┌─────────────────────────────────────────────────────────────────┐
│                    TradingSession                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                Основной цикл торговли                   │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │   │
│  │  │ Проверка    │ │ Получение   │ │ Проверка    │      │   │
│  │  │ торговых    │ │ сигналов    │ │ рисков      │      │   │
│  │  │ часов       │ │             │ │             │      │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Компоненты системы                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│TinkoffAPIClient│    │OrderExecutor │    │PortfolioManager│    │RiskManager │
│             │    │             │    │             │    │             │
│ • get_candles│    │ • buy_market │    │ • get_portfolio│    │ • check_trade_risk│
│ • get_futures│    │ • sell_market│    │ • get_position │    │ • check_stop_loss│
│   _margin    │    │ • cancel_order│    │ • close_position│    │ • check_take_profit│
│ • get_portfolio│    │ • get_order_│    │ • get_guarantee│    │             │
│ • place_order│    │   status     │    │   _deposit   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
        │                   │                   │                   │
        └───────────────────┼───────────────────┼───────────────────┘
                            │                   │
                            ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│SignalManager│    │StrategyManager│    │MarketHours │
│             │    │             │    │             │
│ • add_candle│    │ • on_candle │    │ • get_market│
│ • get_signal│    │ • execute   │    │   _status   │
│ • calculate │    │ • strategies│    │ • is_trading│
│   indicators│    │   [Long,    │    │ • next_session│
│             │    │    Short]   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 🔄 Поток данных

### 1. Инициализация
```
TradingSession.start()
    ├── Проверка торговых часов (MarketHours)
    ├── Инициализация компонентов (_initialize_components)
    │   ├── TinkoffAPIClient (единый экземпляр)
    │   ├── OrderExecutor (получает api_client)
    │   ├── PortfolioManager (получает api_client)
    │   ├── RiskManager (получает portfolio_manager)
    │   ├── SignalManager (с параметрами)
    │   └── StrategyManager (с стратегиями Long/Short)
    └── Запуск основного цикла (run_trading_loop)
```

### 2. Основной цикл торговли
```
run_trading_loop()
    ├── Проверка торговых часов
    ├── Получение сигналов (_process_signals)
    ├── Проверка рисков (_check_risk_limits)
    ├── Обновление статистики (_update_stats)
    └── Пауза 1 секунда
```

### 3. Обработка сигнала
```
execute_signal(signal)
    ├── Получение приказов от стратегий
    │   └── strategy_manager.on_candle(signal.candle)
    │       ├── LongStrategy.execute(signal)
    │       └── ShortStrategy.execute(signal)
    ├── Проверка рисков для каждого приказа
    │   └── risk_manager.check_trade_risk()
    ├── Выполнение приказов
    │   ├── order_executor.buy_market() / sell_market()
    │   └── Обновление статистики
    └── Возврат результата
```

## 🎯 Ключевые особенности

### Единый API клиент
- **TinkoffAPIClient** - централизованная обертка над AsyncClient
- Все компоненты используют один экземпляр
- Автоматическое управление контекстом (__aenter__/__aexit__)

### Управление рисками
- **RiskManager** проверяет каждый приказ перед выполнением
- Стоп-лоссы и тейк-профиты в реальном времени
- Лимиты на размер позиций и потери

### Стратегии
- **LongStrategy** и **ShortStrategy** с единым интерфейсом
- Получение гарантийного обеспечения из API
- Асинхронное выполнение для работы с API

### Портфель
- **PortfolioManager** специализирован на фьючерсах
- Автоматический расчет PnL
- Кэширование данных для производительности

## 📈 Пример использования

```python
# Конфигурация
trading_config = TradingConfig(
    figi="FUTIMOEXF000",
    deposit=100000,
    percent_from_deposit=50,
    items_per_trade=5,
    signal_manager_params={
        'macd_fast': 10,
        'macd_slow': 15,
        'macd_signal': 11,
        'atr_period': 7,
        'lookback_min': 8,
        'lookback_max': 18,
        'peak_prominence': 0.15
    },
    risk_limits=RiskLimits(
        max_position_size=50000,
        max_daily_loss=2500,
        max_portfolio_risk=15,
        max_single_trade=5000,
        stop_loss_percent=3,
        take_profit_percent=8
    )
)

# Запуск
session = TradingSession(
    config=trading_config,
    token=config.tcs_client.token,
    account_id=config.tcs_client.id
)

await session.start()
await session.run_trading_loop()
```

## 🔧 Технические детали

### Асинхронность
- Все операции с API асинхронные
- Стратегии стали асинхронными для работы с API
- Неблокирующий основной цикл

### Обработка ошибок
- Graceful shutdown при ошибках
- Логирование всех операций
- Строгие ошибки API - нет fallback на статические данные

### Производительность
- Кэширование данных портфеля
- Единый API клиент (меньше соединений)
- Оптимизированные запросы к API
