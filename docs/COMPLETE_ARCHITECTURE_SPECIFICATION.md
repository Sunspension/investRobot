# Полная спецификация архитектуры investRobot

## Обзор системы

investRobot - это торговая система для автоматической торговли фьючерсами на основе технических индикаторов (MACD) с использованием Tinkoff Invest API. Система построена на принципах Event-Driven архитектуры с Dependency Injection.

## Архитектурные принципы

### 1. Event-Driven Architecture
- **EventBus** - центральная шина событий для обмена данными между компонентами
- **TradingEvent** - типизированные события с данными
- **EventType** - перечисление типов событий
- **Асинхронная обработка** - все события обрабатываются асинхронно

### 2. Dependency Injection
- **TradingSystemContainer** - DI контейнер для управления зависимостями
- **Интерфейсы** - все компоненты реализуют интерфейсы для тестируемости
- **Инверсия зависимостей** - компоненты не создают зависимости внутри себя

### 3. SOLID принципы
- **Single Responsibility** - каждый класс имеет одну ответственность
- **Open/Closed** - открыт для расширения, закрыт для модификации
- **Liskov Substitution** - интерфейсы могут быть заменены реализациями
- **Interface Segregation** - интерфейсы разделены по функциональности
- **Dependency Inversion** - зависимости инжектируются через интерфейсы

## Основные компоненты

### 1. TradingSystemContainer (DI Container)

**Файл:** `robotlib/trading/di_container.py`

**Назначение:** Центральный контейнер для создания и управления всеми зависимостями системы.

**Основные методы:**
```python
class TradingSystemContainer:
    def __init__(self, config: TradingConfig, enable_visualization: bool = False)
    
    # Основные компоненты
    def get_event_bus(self) -> EventBusable
    def get_session_stats(self) -> SessionStats
    async def get_api_client(self) -> TinkoffAPIClient
    def get_portfolio_manager(self) -> PortfolioManager
    def get_risk_manager(self) -> RiskManager
    def get_order_executor(self) -> OrderExecutor
    def get_signal_manager(self) -> SignalManager
    def get_strategy_manager(self) -> StrategyManager
    async def get_market_data_stream(self) -> MarketDataStream
    async def get_trading_dependencies(self) -> TradingDependencies
    async def get_session_initializer(self) -> SessionInitializer
    async def get_session_controller(self) -> SessionController
    def get_visualizer(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True) -> Optional[DashEventVisualizer]
    
    # Сборка системы
    async def build_trading_system(self, host: str = "127.0.0.1", port: int = 8050, start_server: bool = True) -> Dict[str, Any]
```

**Принципы работы:**
- Singleton pattern для всех компонентов
- Ленивая инициализация - компоненты создаются только при первом обращении
- Асинхронная инициализация API клиента
- Условное создание визуализатора

### 2. EventBus (Шина событий)

**Файл:** `robotlib/trading/event_bus_interface.py`

**Назначение:** Центральная шина для обмена событиями между компонентами.

**Интерфейс:**
```python
class EventBusable(ABC):
    def subscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None
    def unsubscribe(self, event_type: EventType, handler: Callable[[TradingEvent], None]) -> None
    async def publish(self, event: TradingEvent) -> None
    def get_subscribers(self, event_type: EventType) -> List[Callable[[TradingEvent], None]]
```

**Типы событий:**
```python
class EventType(Enum):
    CANDLE_RECEIVED = "candle_received"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_UPDATED = "portfolio_updated"
    MARKET_STATUS_CHANGED = "market_status_changed"
```

**Структура события:**
```python
class TradingEvent:
    def __init__(self, event_type: EventType, data: Dict[str, Any], timestamp: float = None)
    # Свойства:
    # - event_type: EventType
    # - data: Dict[str, Any]
    # - timestamp: float
```

**Реализации:**
- `EventBus` - реальная реализация для продакшна
- `MockEventBus` - мок для тестирования

### 3. SignalManager (Менеджер сигналов)

**Файл:** `robotlib/signal_manager.py`

**Назначение:** Генерация торговых сигналов на основе технических индикаторов MACD.

**Основные методы:**
```python
class SignalManager:
    def __init__(
        self,
        macd_fast=6,
        macd_slow=11,
        macd_signal=9,
        atr_period=7,
        vol_period=14,
        lookback_min=6,
        lookback_max=20,
        peak_prominence=0.2,
        event_bus=None
    )
    
    def add_candle(self, candle: Candle | HistoricCandle) -> Optional[Signal]
    def subscribe_to_events(self)
    async def _handle_candle_event(self, event: TradingEvent)
    
    @property
    def candles(self) -> deque
```

**Алгоритм работы:**
1. Получает свечи через EventBus
2. Вычисляет MACD индикатор (быстрая, медленная, сигнальная линии)
3. Вычисляет ATR для адаптивного окна анализа
4. Обнаруживает пики и впадины в MACD гистограмме
5. Генерирует сигналы на основе пиков/впадин
6. Публикует события сигналов

**Структура сигнала:**
```python
@dataclass
class Signal:
    macd: float = None
    signal: float = None
    histogram: float = None
    macd_prev: float = None
    signal_prev: float = None
    peak_detected: bool = False
    trough_detected: bool = False
    candle: Candle | HistoricCandle = None
```

### 4. PortfolioManager (Менеджер портфеля)

**Файл:** `robotlib/trading/portfolio_manager.py`

**Назначение:** Управление портфелем, позициями и получение информации о балансе.

**Основные методы:**
```python
class PortfolioManager:
    def __init__(self, api_client: TinkoffAPIClient, event_bus: Optional[EventBusable] = None)
    
    async def get_portfolio(self, force_refresh: bool = False) -> Portfolio
    async def get_deposit(self) -> float
    async def get_guarantee_deposit(self, figi: str) -> float
    async def get_position(self, figi: str) -> Optional[Position]
    async def close_position(self, figi: str) -> bool
    async def get_operations_history(self, from_date, to_date) -> List[Operation]
```

**Структуры данных:**
```python
@dataclass
class Position:
    figi: str
    quantity: int
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float

@dataclass
class Portfolio:
    total_amount: float
    blocked_amount: float
    available_amount: float
    positions: List[Position]
    variation_margin: float = 0.0
    guarantee_deposit: float = 0.0
    pnl: float = 0.0
```

**Особенности:**
- Кэширование данных на 30 секунд
- Фильтрация только фьючерсов
- Публикация событий обновления портфеля
- Обработка ошибок API

### 5. SessionController (Контроллер сессии)

**Файл:** `robotlib/trading/session_controller.py`

**Назначение:** Управление жизненным циклом торговой сессии.

**Основные методы:**
```python
class SessionController:
    def __init__(
        self, 
        config: TradingConfig, 
        dependencies: TradingDependencies, 
        force_start: bool = False,
        visualizer: Optional[EventVisualizerable] = None
    )
    
    async def start(self) -> bool
    async def stop(self) -> None
    async def run_trading_loop(self) -> None
    async def _check_market_status(self) -> bool
    async def _wait_for_market_open(self) -> bool
    async def _get_new_candles(self) -> None
    async def _wait_for_api_recovery(self) -> bool
```

**Жизненный цикл сессии:**
1. **Проверка статуса рынка** - проверяет, открыт ли рынок
2. **Инициализация компонентов** - настраивает все зависимости
3. **Ожидание открытия рынка** - если рынок закрыт
4. **Основной торговый цикл** - получение свечей и обработка сигналов
5. **Обработка ошибок** - восстановление после сбоев API

**Особенности:**
- Graceful shutdown при прерывании пользователем
- Корректная очистка ресурсов при любых ошибках

### 6. StrategyManager (Менеджер стратегий)

**Файл:** `robotlib/strategies/strategy_manager.py`

**Назначение:** Управление торговыми стратегиями (Long, Short).

**Основные методы:**
```python
class StrategyManager:
    def __init__(
        self,
        portfolio_manager: PortfolioManageable,
        order_executor: OrderExecutable,
        risk_manager: RiskManageable,
        signal_manager: SignalManageable,
        event_bus: EventBusable
    )
    
    async def initialize(self, figi: str, point_value: float = None, contracts_per_lot: int = None) -> None
    async def on_candle(self, candle) -> None
    async def close_all_positions(self) -> None
    async def _execute_signal(self, signal: Signal) -> None
```

**Стратегии:**
- **LongStrategy** - стратегия покупки
- **ShortStrategy** - стратегия продажи

### 7. OrderExecutor (Исполнитель ордеров)

**Файл:** `robotlib/trading/order_executor.py`

**Назначение:** Выполнение торговых ордеров через API.

**Основные методы:**
```python
class OrderExecutor:
    def __init__(self, api_client: TinkoffAPIClient, event_bus: Optional[EventBusable] = None)
    
    async def execute_order(self, order_intent: OrderIntent) -> OrderExecution
    async def buy_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult
    async def sell_market(self, figi: str, quantity: int, wait_execution: bool = True) -> OrderResult
    async def buy_limit(self, figi: str, quantity: int, price: float) -> OrderResult
    async def sell_limit(self, figi: str, quantity: int, price: float) -> OrderResult
```

**Типы ордеров:**
```python
@dataclass
class OrderIntent:
    figi: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"
    client_order_id: Optional[str] = None

@dataclass
class OrderExecution:
    order_id: str
    figi: str
    direction: OrderDirection
    quantity: int
    filled_quantity: int
    price: float
    status: OrderStatus
    timestamp: datetime
    error_message: Optional[str] = None
    commission: float = 0.0
```

### 8. MarketDataStream (Поток рыночных данных)

**Файл:** `robotlib/trading/market_data_stream.py`

**Назначение:** Получение и кэширование рыночных данных (свечи).

**Основные методы:**
```python
class MarketDataStream:
    def __init__(self, api_client: TinkoffAPIClient, event_bus: EventBusable, figi: str)
    
    async def start(self) -> None
    async def stop(self) -> None
    async def get_latest_candles(self, count: int = 10) -> List[Candle]
    async def get_current_price(self) -> Optional[float]
    def get_cached_candles(self) -> List[Candle]
    def get_cache_size(self) -> int
    def clear_cache(self) -> None
    def add_signal_callback(self, callback) -> None
    def remove_signal_callback(self, callback) -> None
```

**Особенности:**
- Кэширование свечей в памяти
- Публикация событий о новых свечах
- Ограничение размера кэша (1000 свечей)
- Асинхронное получение данных

### 9. RiskManager (Менеджер рисков)

**Файл:** `robotlib/trading/risk_manager.py`

**Назначение:** Управление торговыми рисками и лимитами.

**Основные методы:**
```python
class RiskManager:
    def __init__(self, risk_limits: RiskLimits)
    
    @property
    def risk_limits(self) -> RiskLimits
    
    async def check_trade_risk(self, figi: str, quantity: int, price: float) -> RiskCheck
    async def check_stop_loss(self, figi: str) -> Optional[RiskCheck]
    async def get_risk_report(self) -> Dict[str, Any]
```

**Структуры данных:**
```python
@dataclass
class RiskLimits:
    max_position_size: int
    max_daily_loss: float
    max_single_trade: float
    stop_loss_percent: float

@dataclass
class RiskCheck:
    is_approved: bool
    risk_level: str
    message: str
    suggested_action: Optional[str] = None
```

### 10. DashEventVisualizer (Визуализатор)

**Файл:** `visualization/dash_event_visualizer.py`

**Назначение:** Визуализация торговых данных и событий через веб-интерфейс.

**Основные методы:**
```python
class DashEventVisualizer:
    def __init__(
        self, 
        event_bus: EventBusable, 
        figi: str = "FUTIMOEXF000", 
        host: str = "127.0.0.1", 
        port: int = 8050,
        start_server: bool = True
    )
    
    async def start(self) -> None
    async def stop(self) -> None
    def _create_dash_app(self) -> Dash
    def _setup_event_handlers(self) -> None
    def _run_server(self) -> None
```

**Компоненты визуализации:**
- **DataManager** - управление данными для отображения
- **ChartBuilder** - построение графиков
- **UIComponents** - компоненты интерфейса

## Архитектурная диаграмма

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TradingSystemContainer (DI)                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                EventBus                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ CANDLE_RECEIVED │  │ SIGNAL_GENERATED│  │ ORDER_PLACED    │  │ PORTFOLIO_  │ │
│  │                 │  │                 │  │                 │  │ UPDATED     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Основные компоненты                                 │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │SignalManager │    │PortfolioMgr  │    │OrderExecutor │    │RiskManager   │  │
│  │              │    │              │    │              │    │              │  │
│  │- MACD calc   │    │- Portfolio   │    │- Buy/Sell    │    │- Risk limits │  │
│  │- Peak detect │    │- Positions   │    │- Order mgmt  │    │- Risk check  │  │
│  │- Signal gen  │    │- Balance     │    │- Execution   │    │- Reports     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │StrategyMgr   │    │MarketDataStr │    │SessionCtrl   │    │TradingConfig │  │
│  │              │    │              │    │              │    │              │  │
│  │- Long/Short  │    │- Candle cache│    │- Lifecycle   │    │- Settings    │  │
│  │- Signal exec │    │- Data stream │    │- Market check│    │- Parameters  │  │
│  │- Position mgmt│   │- Event pub   │    │- Error handle│    │- Timeouts    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Внешние системы                                   │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │Tinkoff API   │    │Dash Visualizer│   │File System   │    │Logging       │  │
│  │              │    │              │    │              │    │              │  │
│  │- Market data │    │- Web UI      │    │- Config      │    │- Console     │  │
│  │- Orders      │    │- Charts      │    │- Logs        │    │- Files       │  │
│  │- Portfolio   │    │- Real-time   │    │- Data        │    │- Levels      │  │
│  │- Positions   │    │- Statistics  │    │- Cache       │    │- Rotation    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Потоки данных

### 1. Основной торговый поток

```
MarketDataStream → EventBus → SignalManager → StrategyManager → OrderExecutor → PortfolioManager
```

1. **MarketDataStream** получает свечи от API
2. **EventBus** передает событие `CANDLE_RECEIVED`
3. **SignalManager** обрабатывает свечу и генерирует сигнал
4. **EventBus** передает событие `SIGNAL_GENERATED`
5. **StrategyManager** получает сигнал и принимает решение о торговле
6. **OrderExecutor** выполняет ордер
7. **PortfolioManager** обновляет портфель

### 2. Поток визуализации

```
EventBus → DashEventVisualizer → DataManager → UIComponents → Dash App
```

1. **EventBus** передает все события
2. **DashEventVisualizer** подписывается на события
3. **DataManager** сохраняет данные для отображения
4. **UIComponents** обновляет интерфейс
5. **Dash App** отображает данные в браузере

### 3. Поток управления сессией

```
SessionController → SessionInitializer → TradingDependencies → EventBus
```

1. **SessionController** управляет жизненным циклом
2. **SessionInitializer** инициализирует компоненты
3. **TradingDependencies** связывает все зависимости
4. **EventBus** обеспечивает связь между компонентами

## Конфигурация

### TradingConfig

**Файл:** `robotlib/trading/trading_config.py`

```python
class TradingConfig:
    def __init__(
        self, 
        figi: str, 
        auto_close_positions: bool = True,
        end_of_day_close: bool = True,
        close_time: time = time(23, 50),
        warning_periods: list[int] = [600, 300, 60],
        enable_visualization: bool = False
    )
```

**Параметры:**
- `figi` - идентификатор инструмента
- `auto_close_positions` - автоматическое закрытие позиций
- `end_of_day_close` - закрытие в конце дня
- `close_time` - время закрытия позиций
- `warning_periods` - периоды предупреждений
- `enable_visualization` - включение визуализации

## Интерфейсы

### Основные интерфейсы

**Файл:** `robotlib/trading/interfaces.py`

1. **TinkoffAPIClientable** - интерфейс для API клиента
2. **OrderExecutable** - интерфейс для исполнителя ордеров
3. **SignalManageable** - интерфейс для менеджера сигналов
4. **StrategyManageable** - интерфейс для менеджера стратегий
5. **MarketDataStreamable** - интерфейс для потока данных
6. **PortfolioManageable** - интерфейс для менеджера портфеля
7. **RiskManageable** - интерфейс для менеджера рисков

### TradingDependencies

**Контейнер для всех зависимостей:**
```python
@dataclass
class TradingDependencies:
    api_client: APIClientable
    order_executor: OrderExecutable
    portfolio_manager: PortfolioManageable
    risk_manager: RiskManageable
    signal_manager: SignalManageable
    strategy_manager: StrategyManageable
    market_data_stream: MarketDataStreamable
    session_stats: SessionStatsable
```

## Типы данных

### Signal

**Файл:** `robotlib/signal_types.py`

```python
@dataclass
class Signal:
    macd: float = None
    signal: float = None
    histogram: float = None
    macd_prev: float = None
    signal_prev: float = None
    peak_detected: bool = False
    trough_detected: bool = False
    candle: Candle | HistoricCandle = None
```

### Order Types

**Файл:** `robotlib/trading/order_types.py`

```python
class OrderDirection(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
```

## Запуск системы

### Основной entry point

**Файл:** `run_trading_system.py`

```python
async def run_trading_system(
    figi: str = "FUTIMOEXF000",
    enable_visualization: bool = True,
    host: str = "127.0.0.1",
    port: int = 8050
):
    # Загрузка конфигурации
    config = load_config()
    
    # Создание торговой конфигурации
    trading_config = TradingConfig(
        figi=figi,
        enable_visualization=enable_visualization
    )
    
    # Создание DI контейнера
    container = TradingSystemContainer(trading_config, enable_visualization=enable_visualization)
    trading_system = await container.build_trading_system(host=host, port=port)
    
    # Запуск системы
    session_controller = trading_system['session_controller']
    await session_controller.start()
```

### С моками для тестирования

**Файл:** `run_trading_system_with_mocks.py`

Аналогично основному, но с мок-данными вместо реального API.

## Тестирование

### Структура тестов

**Папка:** `tests/`

- **test_di_container.py** - тесты DI контейнера
- **test_event_integration.py** - тесты интеграции событий
- **test_signal_manager.py** - тесты менеджера сигналов
- **test_portfolio_manager.py** - тесты менеджера портфеля
- **test_strategies.py** - тесты стратегий
- **test_trading_system_with_di.py** - тесты торговой системы

### Принципы тестирования

1. **Моки для всех внешних зависимостей** - API, база данных, файлы
2. **Изоляция тестов** - каждый тест независим
3. **Проверка интерфейсов** - тестирование через интерфейсы
4. **Асинхронные тесты** - использование pytest-asyncio

## Логирование

### Система логирования

**Файл:** `robotlib/utils/logger.py`

```python
def get_logger(name: str) -> logging.Logger:
    # Настройка логов с уровнем INFO
    # Формат: время, уровень, модуль, сообщение
    # Вывод в консоль и файл
```

### Уровни логирования

- **DEBUG** - отладочная информация
- **INFO** - общая информация о работе
- **WARNING** - предупреждения
- **ERROR** - ошибки
- **CRITICAL** - критические ошибки

## Обработка ошибок

### Принципы обработки ошибок

1. **Логирование всех ошибок** - с контекстом и стеком вызовов
2. **Graceful degradation** - система продолжает работать при ошибках
3. **Восстановление после сбоев** - автоматическое восстановление API
4. **Валидация данных** - проверка входных данных

### Типы ошибок

1. **API ошибки** - проблемы с Tinkoff API
2. **Сетевые ошибки** - проблемы с сетью
3. **Ошибки данных** - некорректные данные
4. **Ошибки конфигурации** - неправильная настройка

## Производительность

### Оптимизации

1. **Кэширование** - кэш портфеля, свечей, статуса рынка
2. **Ленивая инициализация** - компоненты создаются по требованию
3. **Асинхронность** - неблокирующие операции
4. **Ограничение памяти** - ограничение размера кэшей

### Мониторинг

1. **Логирование производительности** - время выполнения операций
2. **Метрики системы** - использование памяти, CPU
3. **Статистика торговли** - количество сделок, прибыль/убыток

## Безопасность

### Принципы безопасности

1. **Токены API** - хранение в конфигурации, не в коде
2. **Валидация данных** - проверка всех входных данных
3. **Обработка ошибок** - не раскрытие чувствительной информации
4. **Логирование** - не логирование чувствительных данных

## Расширяемость

### Добавление новых компонентов

1. **Создание интерфейса** - определение контракта
2. **Реализация интерфейса** - создание класса
3. **Регистрация в DI** - добавление в контейнер
4. **Интеграция с EventBus** - подписка на события

### Добавление новых стратегий

1. **Создание класса стратегии** - наследование от базового
2. **Реализация методов** - on_candle, execute_signal
3. **Регистрация в StrategyManager** - добавление в список
4. **Тестирование** - создание тестов

## Детальные примеры кода

### 1. Создание и запуск системы

```python
# Основной entry point
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from config_data.config import load_config

async def main():
    # Загрузка конфигурации
    config = load_config()
    
    # Создание торговой конфигурации
    trading_config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    trading_config.tcs_client = config.tcs_client
    
    # Создание DI контейнера
    container = TradingSystemContainer(trading_config, enable_visualization=True)
    
    # Сборка торговой системы
    trading_system = await container.build_trading_system(
        host="127.0.0.1", 
        port=8050, 
        start_server=True
    )
    
    # Получение компонентов
    session_controller = trading_system['session_controller']
    event_bus = trading_system['event_bus']
    visualizer = trading_system['visualizer']
    
    # Запуск системы
    await session_controller.start()

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Работа с EventBus

```python
from robotlib.trading.event_bus_interface import EventBus, EventType, TradingEvent

# Создание шины событий
event_bus = EventBus()

# Подписка на события
def handle_candle(event: TradingEvent):
    candle = event.data['candle']
    print(f"Получена свеча: {candle.close}")

def handle_signal(event: TradingEvent):
    signal = event.data['signal']
    print(f"Сгенерирован сигнал: {signal.peak_detected}")

event_bus.subscribe(EventType.CANDLE_RECEIVED, handle_candle)
event_bus.subscribe(EventType.SIGNAL_GENERATED, handle_signal)

# Публикация события
candle_event = TradingEvent(
    EventType.CANDLE_RECEIVED,
    {'candle': candle_data, 'figi': 'FUTIMOEXF000'}
)
await event_bus.publish(candle_event)
```

### 3. Создание SignalManager

```python
from robotlib.signal_manager import SignalManager
from robotlib.trading.event_bus_interface import EventBus

# Создание менеджера сигналов
signal_manager = SignalManager(
    macd_fast=6,
    macd_slow=11,
    macd_signal=9,
    atr_period=7,
    vol_period=14,
    lookback_min=6,
    lookback_max=20,
    peak_prominence=0.2,
    event_bus=event_bus
)

# Подписка на события свечей
signal_manager.subscribe_to_events()

# Добавление свечи (автоматически через EventBus)
# signal_manager.add_candle(candle) - вызывается автоматически
```

### 4. Работа с PortfolioManager

```python
from robotlib.trading.portfolio_manager import PortfolioManager
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient

# Создание менеджера портфеля
portfolio_manager = PortfolioManager(api_client, event_bus)

# Получение портфеля
portfolio = await portfolio_manager.get_portfolio()
print(f"Общая сумма: {portfolio.total_amount}")
print(f"Доступно: {portfolio.available_amount}")

# Получение позиции
position = await portfolio_manager.get_position("FUTIMOEXF000")
if position:
    print(f"Позиция: {position.quantity} контрактов")
    print(f"Средняя цена: {position.average_price}")

# Получение депозита
deposit = await portfolio_manager.get_deposit()
print(f"Депозит: {deposit}")
```

### 5. Выполнение ордеров

```python
from robotlib.trading.order_executor import OrderExecutor
from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType

# Создание исполнителя ордеров
order_executor = OrderExecutor(api_client, event_bus)

# Создание намерения на ордер
order_intent = OrderIntent(
    figi="FUTIMOEXF000",
    direction=OrderDirection.BUY,
    order_type=OrderType.MARKET,
    quantity=1
)

# Выполнение ордера
execution = await order_executor.execute_order(order_intent)
print(f"Ордер выполнен: {execution.order_id}")
print(f"Статус: {execution.status}")

# Простые методы
result = await order_executor.buy_market("FUTIMOEXF000", 1)
result = await order_executor.sell_market("FUTIMOEXF000", 1)
result = await order_executor.buy_limit("FUTIMOEXF000", 1, 2900.0)
```

### 6. Управление стратегиями

```python
from robotlib.strategies.strategy_manager import StrategyManager
from robotlib.strategies.long import LongStrategy
from robotlib.strategies.short import ShortStrategy

# Создание менеджера стратегий
strategy_manager = StrategyManager(
    portfolio_manager=portfolio_manager,
    order_executor=order_executor,
    risk_manager=risk_manager,
    signal_manager=signal_manager,
    event_bus=event_bus
)

# Инициализация стратегий
await strategy_manager.initialize(
    figi="FUTIMOEXF000",
    point_value=1.0,
    contracts_per_lot=1
)

# Обработка свечи через стратегии
await strategy_manager.on_candle(candle_data)

# Закрытие всех позиций
await strategy_manager.close_all_positions()
```

### 7. Работа с MarketDataStream

```python
from robotlib.trading.market_data_stream import MarketDataStream

# Создание потока данных
market_data_stream = MarketDataStream(api_client, event_bus, "FUTIMOEXF000")

# Запуск потока
await market_data_stream.start()

# Получение последних свечей
candles = await market_data_stream.get_latest_candles(10)
print(f"Получено {len(candles)} свечей")

# Получение текущей цены
current_price = await market_data_stream.get_current_price()
print(f"Текущая цена: {current_price}")

# Получение кэшированных свечей
cached_candles = market_data_stream.get_cached_candles()
print(f"В кэше {len(cached_candles)} свечей")

# Остановка потока
await market_data_stream.stop()
```

### 8. Управление рисками

```python
from robotlib.trading.risk_manager import RiskManager, RiskLimits

# Создание лимитов рисков
risk_limits = RiskLimits(
    max_position_size=10,
    max_daily_loss=10000.0,
    max_single_trade=1000.0,
    stop_loss_percent=5.0
)

# Создание менеджера рисков
risk_manager = RiskManager(risk_limits)

# Проверка риска сделки
risk_check = await risk_manager.check_trade_risk(
    figi="FUTIMOEXF000",
    quantity=1,
    price=2900.0
)

if risk_check.is_approved:
    print("Сделка одобрена")
else:
    print(f"Сделка отклонена: {risk_check.message}")

# Получение отчета о рисках
risk_report = await risk_manager.get_risk_report()
print(f"Отчет о рисках: {risk_report}")
```

### 9. Визуализация

```python
from visualization.dash_event_visualizer import DashEventVisualizer

# Создание визуализатора
visualizer = DashEventVisualizer(
    event_bus=event_bus,
    figi="FUTIMOEXF000",
    host="127.0.0.1",
    port=8050,
    start_server=True
)

# Запуск визуализатора
await visualizer.start()

# Визуализатор будет доступен по адресу http://127.0.0.1:8050
# Автоматически подписывается на все события и отображает их в веб-интерфейсе
```

### 10. Полный пример интеграции

```python
import asyncio
from robotlib.trading.di_container import TradingSystemContainer
from robotlib.trading.trading_config import TradingConfig
from config_data.config import load_config

async def run_complete_system():
    """Полный пример запуска торговой системы"""
    
    # 1. Загрузка конфигурации
    config = load_config()
    trading_config = TradingConfig(
        figi="FUTIMOEXF000",
        enable_visualization=True
    )
    trading_config.tcs_client = config.tcs_client
    
    # 2. Создание DI контейнера
    container = TradingSystemContainer(trading_config, enable_visualization=True)
    
    # 3. Сборка системы
    trading_system = await container.build_trading_system()
    
    # 4. Получение компонентов
    session_controller = trading_system['session_controller']
    event_bus = trading_system['event_bus']
    visualizer = trading_system['visualizer']
    
    # 5. Настройка обработчиков событий
    def log_event(event):
        print(f"Событие: {event.event_type.value} - {event.data}")
    
    event_bus.subscribe(EventType.CANDLE_RECEIVED, log_event)
    event_bus.subscribe(EventType.SIGNAL_GENERATED, log_event)
    event_bus.subscribe(EventType.ORDER_PLACED, log_event)
    
    # 6. Запуск системы
    print("Запуск торговой системы...")
    success = await session_controller.start()
    
    if success:
        print("Торговая система запущена успешно!")
        print(f"Визуализатор доступен по адресу: http://127.0.0.1:8050")
        
        # Система будет работать до остановки
        try:
            await session_controller.run_trading_loop()
        except KeyboardInterrupt:
            print("Остановка системы...")
            await session_controller.stop()
    else:
        print("Не удалось запустить торговую систему")

if __name__ == "__main__":
    asyncio.run(run_complete_system())
```

## Заключение

Данная спецификация описывает полную архитектуру системы investRobot. Система построена на принципах Event-Driven архитектуры с Dependency Injection, что обеспечивает высокую тестируемость, расширяемость и поддерживаемость кода.

Основные преимущества архитектуры:
- **Модульность** - каждый компонент независим
- **Тестируемость** - легко тестировать через интерфейсы
- **Расширяемость** - легко добавлять новые компоненты
- **Поддерживаемость** - четкое разделение ответственности
- **Производительность** - асинхронная обработка и кэширование

Система готова к продакшн использованию и может быть легко расширена новыми функциями и стратегиями.


**Эта спецификация содержит всю необходимую информацию для полного воссоздания системы с нуля.**
