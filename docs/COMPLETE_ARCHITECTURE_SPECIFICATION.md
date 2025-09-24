# Полная спецификация архитектуры investRobot

## Обзор системы

investRobot - это торговая система для автоматической торговли фьючерсами на основе технических индикаторов (MACD/ATR) с использованием Tinkoff Invest API. Система построена на принципах асинхронной архитектуры и Dependency Injection.

## Архитектурные принципы

### 1. Прямые обновления без центральной шины
- **VisualizationSinkable** — прямой sink-интерфейс (`on_candle`, `on_signal`, `on_market_status`) для UI
- **SignalDispatcher** — тонкий слой доставки сигналов из application-уровня (управляется `StrategyManager`)
- **Асинхронная обработка** — прямые вызовы без EventBus

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

### 2. Сигналы и визуализация

**Интерфейсы:**

**Sink-интерфейс:**
```python
class VisualizationSinkable(Protocol):
    async def on_candle(self, candle) -> None: ...
    async def on_signal(self, signal) -> None: ...
    async def on_market_status(self, status) -> None: ...
```

**Диспетчер сигналов:**
```python
class SignalDispatchable(Protocol):
    async def dispatch_signal(self, signal: Signal, figi: str, price: float) -> None: ...

class VisualizationSignalDispatcher(SignalDispatchable):
    def __init__(self, sink: VisualizationSinkable): ...
    async def dispatch_signal(self, signal, figi, price): await sink.on_signal(signal, figi, price)
```
Передача в UI осуществляется через `StrategyManager` → `SignalDispatcher` → `VisualizationSinkable`.

### 3. SignalManager (Менеджер сигналов)

**Файл:** `robotlib/signal_manager.py`

**Назначение:** Генерация торговых сигналов на основе MACD/ATR.

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
        peak_prominence=0.2
    )
    
    def add_candle(self, candle: Candle | HistoricCandle) -> Optional[Signal]
    # Прямой вызов из MarketDataStream
    async def _handle_candle(self, candle: Candle | HistoricCandle)
    
    @property
    def candles(self) -> deque
```

**Алгоритм работы:**
1. Получает свечи напрямую из `MarketDataStream`
2. Вычисляет MACD индикатор (быстрая, медленная, сигнальная линии)
3. Вычисляет ATR для адаптивного окна анализа
4. Обнаруживает пики и впадины в MACD гистограмме
5. Генерирует сигналы
6. Возвращает `Signal` наверх; доставка сигнала во внешний мир выполняется `StrategyManager` через `SignalDispatcher`

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
    def __init__(self, api_client: TinkoffAPIClient)
    
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
        signal_manager: SignalManageable
        signal_dispatcher: Optional[SignalDispatchable] = None
    )
    
    async def initialize(self, figi: str, point_value: float = None, contracts_per_lot: int = None) -> None
    async def on_candle(self, candle) -> None  # при наличии dispatcher вызывает dispatch_signal
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
    def __init__(self, api_client: TinkoffAPIClient)
    
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
    def __init__(self, api_client: TinkoffAPIClient, figi: str)
    
    async def start(self) -> None
    async def stop(self) -> None
    def set_event_sink(self, sink: VisualizationSinkable) -> None
```

**Особенности:**
- Кэширование свечей в памяти
- Отправка свечей в визуализатор через sink (при наличии)
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
    
    async def check_trade_risk(self, figi: str, quantity: int, direction: str) -> RiskCheck
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
        figi: str = "FUTIMOEXF000", 
        host: str = "127.0.0.1", 
        port: int = 8050,
        start_server: bool = True
    )
    
    async def start(self) -> None
    async def stop(self) -> None
    def _create_dash_app(self) -> Dash
    # Визуализатор получает данные через sink-интерфейс
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
│                         Direct calls to Visualization Sink                      │
│    on_candle / on_signal / on_market_status                                     │
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
│  │- Peak detect │    │- Positions   │    │- Order mgmt  │    │- Reports     │  │
│  │- Signal gen  │    │- Balance     │    │- Execution   │    │- Checks      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │StrategyMgr   │    │MarketDataStr │    │SessionCtrl   │    │TradingConfig │  │
│  │              │    │              │    │              │    │              │  │
│  │- Long/Short  │    │- Candle cache│    │- Lifecycle   │    │- Settings    │  │
│  │- Signal exec │    │- Data stream │    │- Market check│    │- Parameters  │  │
│  │- Position mgmt│   │- Sink calls  │    │- Error handle│    │- Timeouts    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Потоки данных

### 1. Основной торговый поток

```
MarketDataStream → SignalManager → StrategyManager → OrderExecutor → PortfolioManager
```

1. **MarketDataStream** получает свечи от API
2. **SignalManager** обрабатывает свечу и генерирует сигнал
3. **StrategyManager** принимает решение о торговле
4. **OrderExecutor** выполняет ордер
5. **PortfolioManager** обновляет портфель

### 2. Поток визуализации

```
MarketDataStream/SignalManager → (direct) Visualization Sink → DataManager → UIComponents → Dash App
```

1. Компоненты вызывают методы `on_*` визуализатора напрямую
2. **DataManager** сохраняет данные для отображения
3. **UIComponents** обновляет интерфейс
4. **Dash App** отображает данные в браузере

### 3. Поток управления сессией

```
SessionController → SessionInitializer → TradingDependencies
```

1. **SessionController** управляет жизненным циклом
2. **SessionInitializer** инициализирует компоненты
3. **TradingDependencies** связывает все зависимости

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
    visualizer = trading_system['visualizer']
    
    # 5. Настройка обработчиков (опционально для отладки)
    def log_event(event):
        print(f"Событие: {getattr(event, 'event_type', 'n/a')} - {getattr(event, 'data', {})}")
    
    # Подписок больше нет — визуализатор получает данные через прямые вызовы sink
    
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
