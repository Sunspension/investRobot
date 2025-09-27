# Go Migration Specification

## 📋 Обзор проекта

**Цель:** Полная миграция Python торговой системы на Go с сохранением всей функциональности и архитектуры.

**Текущий проект:** `investRobot` - торговая система для работы с Tinkoff Invest API
**Целевой проект:** Go версия с идентичной функциональностью

## 🎯 Функциональные требования

### 1. Основная функциональность
- ✅ **Торговля через Tinkoff Invest API** (sandbox + production)
- ✅ **Управление портфелем и позициями**
- ✅ **Исполнение ордеров** (market/limit orders)
- ✅ **Управление рисками** (stop-loss, take-profit, лимиты)
- ✅ **Торговые стратегии** (Long/Short с FIFO логикой)
- ✅ **Поток рыночных данных** (свечи, стаканы)
- ✅ **Синхронизация позиций** с API
- ✅ **Восстановление позиций** из истории операций
- ✅ **Веб-интерфейс** для мониторинга (real-time)
- ✅ **Логирование и мониторинг**

### 2. Торговые возможности
- ✅ **Поддержка фьючерсов** (FUTIMOEXF000)
- ✅ **Long/Short стратегии**
- ✅ **FIFO расчеты** для позиций
- ✅ **Stop-loss/Take-profit** автоматически
- ✅ **Управление размером позиции**
- ✅ **Контроль рисков** (максимальные потери)

### 3. API интеграция
- ✅ **Tinkoff Invest API** (полная поддержка)
- ✅ **Аутентификация** (токены, sandbox)
- ✅ **Rate limiting** и retry логика
- ✅ **Обработка ошибок** API

## 🏗️ Архитектура системы

### 1. Основные компоненты

#### **TradingSystemContainer (DI Container)**
```go
type Container struct {
    config *Config
    instances map[string]interface{}
    mu sync.RWMutex
}

// Основные методы
func (c *Container) GetAPIClient() *investapi.Client
func (c *Container) GetPortfolioManager() *PortfolioManager
func (c *Container) GetOrderExecutor() *OrderExecutor
func (c *Container) GetPositionManager() *PositionManager
func (c *Container) GetRiskManager() *RiskManager
func (c *Container) GetStrategyManager() *StrategyManager
func (c *Container) GetMarketDataStream() *MarketDataStream
func (c *Container) GetSessionController() *SessionController
```

#### **TinkoffAPIClient**
```go
type APIClient struct {
    client *investapi.Client
    config *APIConfig
    logger *logrus.Logger
}

// Основные методы
func (c *APIClient) GetPortfolio() (*investapi.PortfolioResponse, error)
func (c *APIClient) GetPositions() (*investapi.PositionsResponse, error)
func (c *APIClient) PostOrder(req *investapi.PostOrderRequest) (*investapi.PostOrderResponse, error)
func (c *APIClient) GetOrderStatus(orderID string) (*investapi.OrderState, error)
func (c *APIClient) CancelOrder(orderID string) error
func (c *APIClient) GetOperations(req *investapi.OperationsRequest) (*investapi.OperationsResponse, error)
func (c *APIClient) GetCandles(req *investapi.GetCandlesRequest) (*investapi.GetCandlesResponse, error)
func (c *APIClient) CreateMarketDataStream() (*investapi.MarketDataStreamClient, error)
```

#### **OrderExecutor**
```go
type OrderExecutor struct {
    apiClient *APIClient
    logger *logrus.Logger
}

func (e *OrderExecutor) ExecuteOrder(order *Order) (*OrderResult, error)
func (e *OrderExecutor) CancelOrder(orderID string) error
func (e *OrderExecutor) GetOrderStatus(orderID string) (*OrderState, error)
func (e *OrderExecutor) WaitForExecution(orderID string, timeout time.Duration) (*OrderResult, error)
```

#### **PortfolioManager**
```go
type PortfolioManager struct {
    apiClient *APIClient
    db *gorm.DB
    logger *logrus.Logger
}

func (p *PortfolioManager) GetPortfolio() (*Portfolio, error)
func (p *PortfolioManager) GetPositions() ([]*Position, error)
func (p *PortfolioManager) GetPosition(figi string) (*Position, error)
func (p *PortfolioManager) GetPointValue(figi string) (float64, error)
```

#### **PositionManager**
```go
type PositionManager struct {
    db *gorm.DB
    riskManager *RiskManager
    syncService *PositionSyncService
    logger *logrus.Logger
}

func (p *PositionManager) GetPosition(figi string) (*Position, error)
func (p *PositionManager) AddToFIFO(entry *FIFOEntry) error
func (p *PositionManager) GetLossPositions() ([]*LossPosition, error)
func (p *PositionManager) GetProfitPositions() ([]*ProfitPosition, error)
func (p *PositionManager) SyncOnStartup() error
```

#### **RiskManager**
```go
type RiskManager struct {
    config *RiskConfig
    logger *logrus.Logger
}

func (r *RiskManager) CheckTradeRisk(trade *Trade) error
func (r *RiskManager) CheckStopLoss(position *Position) bool
func (r *RiskManager) CheckTakeProfit(position *Position) bool
func (r *RiskManager) GetRiskLimits() *RiskLimits
```

#### **StrategyManager**
```go
type StrategyManager struct {
    strategies []Strategy
    positionManager *PositionManager
    orderExecutor *OrderExecutor
    logger *logrus.Logger
}

func (s *StrategyManager) ProcessSignal(signal *Signal) error
func (s *StrategyManager) ProcessExecution(execution *OrderExecution) error
func (s *StrategyManager) CheckStopLosses() error
```

#### **MarketDataStream**
```go
type MarketDataStream struct {
    client *investapi.MarketDataStreamClient
    cache *CandleCache
    logger *logrus.Logger
}

func (s *MarketDataStream) Start() error
func (s *MarketDataStream) Stop() error
func (s *MarketDataStream) GetCandles(figi string, limit int) ([]*Candle, error)
func (s *MarketDataStream) SubscribeCandles(figi string) error
```

#### **SessionController**
```go
type SessionController struct {
    dependencies *TradingDependencies
    marketHours *MarketHours
    logger *logrus.Logger
}

func (s *SessionController) Start() error
func (s *SessionController) Stop() error
func (s *SessionController) IsTradingTime() bool
func (s *SessionController) GetMarketStatus() *MarketStatus
```

### 2. Модели данных

#### **Order**
```go
type Order struct {
    ID string `gorm:"primaryKey"`
    AccountID string
    FIGI string
    Time time.Time
    Direction OrderDirection
    Price float64
    Quantity int
    Status OrderStatus
    Commission float64
    Strategy string
    Reason string
    OperationID string
    TradeID string
    ExecutionTime time.Time
}
```

#### **Position**
```go
type Position struct {
    FIGI string `gorm:"primaryKey"`
    Quantity int
    AveragePrice float64
    CurrentPrice float64
    UnrealizedPnL float64
    RealizedPnL float64
}
```

#### **FIFOEntry**
```go
type FIFOEntry struct {
    ID string `gorm:"primaryKey"`
    FIGI string
    Quantity int
    Price float64
    Timestamp time.Time
    OrderID string
    Direction OrderDirection
}
```

#### **Portfolio**
```go
type Portfolio struct {
    TotalAmount float64
    Positions []*Position
    PnL float64
    Margin float64
    FreeMargin float64
    VariationMargin float64
    GuaranteeDeposit float64
    LastUpdate time.Time
}
```

### 3. Интерфейсы

#### **Strategy Interface**
```go
type Strategy interface {
    ProcessSignal(signal *Signal) (*OrderIntent, error)
    ProcessExecution(execution *OrderExecution) error
    GetPositionContext() *PositionContext
}
```

#### **RiskManageable Interface**
```go
type RiskManageable interface {
    CheckTradeRisk(trade *Trade) error
    CheckStopLoss(position *Position) bool
    CheckTakeProfit(position *Position) bool
    GetRiskLimits() *RiskLimits
}
```

#### **PortfolioManageable Interface**
```go
type PortfolioManageable interface {
    GetPortfolio() (*Portfolio, error)
    GetPositions() ([]*Position, error)
    GetPosition(figi string) (*Position, error)
    GetPointValue(figi string) (float64, error)
}
```

## 🧪 Тестирование

### 1. Структура тестов

```
tests/
├── unit/                    # Unit тесты
│   ├── api/
│   ├── portfolio/
│   ├── orders/
│   ├── positions/
│   ├── risk/
│   ├── strategies/
│   └── market/
├── integration/             # Интеграционные тесты
│   ├── trading_flow_test.go
│   ├── position_sync_test.go
│   └── risk_management_test.go
├── e2e/                     # End-to-end тесты
│   ├── full_trading_test.go
│   └── web_interface_test.go
└── mocks/                   # Mock объекты
    ├── api_client_mock.go
    ├── portfolio_mock.go
    └── order_executor_mock.go
```

### 2. Критические тесты для миграции

#### **Unit тесты**
- ✅ **APIClient** - все методы API
- ✅ **OrderExecutor** - исполнение ордеров
- ✅ **PortfolioManager** - управление портфелем
- ✅ **PositionManager** - FIFO логика
- ✅ **RiskManager** - проверки рисков
- ✅ **StrategyManager** - обработка сигналов
- ✅ **MarketDataStream** - поток данных

#### **Integration тесты**
- ✅ **TradingFlow** - полный торговый цикл
- ✅ **PositionSync** - синхронизация с API
- ✅ **RiskManagement** - управление рисками
- ✅ **StrategyExecution** - выполнение стратегий

#### **E2E тесты**
- ✅ **FullTrading** - полная торговая сессия
- ✅ **WebInterface** - веб-интерфейс
- ✅ **ErrorHandling** - обработка ошибок

### 3. Mock объекты

#### **MockAPIClient**
```go
type MockAPIClient struct {
    PortfolioResponse *investapi.PortfolioResponse
    PositionsResponse *investapi.PositionsResponse
    OrderResponse *investapi.PostOrderResponse
    Error error
}

func (m *MockAPIClient) GetPortfolio() (*investapi.PortfolioResponse, error) {
    return m.PortfolioResponse, m.Error
}
```

#### **MockOrderExecutor**
```go
type MockOrderExecutor struct {
    ExecuteOrderFunc func(*Order) (*OrderResult, error)
    CancelOrderFunc func(string) error
}

func (m *MockOrderExecutor) ExecuteOrder(order *Order) (*OrderResult, error) {
    return m.ExecuteOrderFunc(order)
}
```

## 🔧 Конфигурация

### 1. Config структура
```go
type Config struct {
    Tinkoff TinkoffConfig `yaml:"tinkoff"`
    Trading TradingConfig `yaml:"trading"`
    Database DatabaseConfig `yaml:"database"`
    Web WebConfig `yaml:"web"`
    Logging LoggingConfig `yaml:"logging"`
}

type TinkoffConfig struct {
    Token string `yaml:"token"`
    SandboxToken string `yaml:"sandbox_token"`
    AccountID string `yaml:"account_id"`
    Sandbox bool `yaml:"sandbox"`
}

type TradingConfig struct {
    FIGI string `yaml:"figi"`
    EnableVisualization bool `yaml:"enable_visualization"`
    PositionsDBPath string `yaml:"positions_db_path"`
    MarketDBPath string `yaml:"market_db_path"`
}
```

### 2. Environment variables
```bash
TINKOFF_TOKEN=your_token
TINKOFF_SANDBOX_TOKEN=your_sandbox_token
TINKOFF_ACCOUNT_ID=your_account_id
TINKOFF_SANDBOX=true
FIGI=FUTIMOEXF000
ENABLE_VISUALIZATION=true
```

## 📊 База данных

### 1. Схема таблиц

#### **orders**
```sql
CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    figi TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    direction TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL,
    commission REAL,
    strategy TEXT,
    reason TEXT,
    operation_id TEXT,
    trade_id TEXT,
    execution_time TIMESTAMP
);
```

#### **positions**
```sql
CREATE TABLE positions (
    figi TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    last_update TIMESTAMP NOT NULL
);
```

#### **position_fifo**
```sql
CREATE TABLE position_fifo (
    id TEXT PRIMARY KEY,
    figi TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price REAL NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    order_id TEXT NOT NULL,
    direction TEXT NOT NULL
);
```

#### **candles**
```sql
CREATE TABLE candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    figi TEXT NOT NULL,
    time TIMESTAMP NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER NOT NULL
);
```

### 2. GORM модели
```go
type Order struct {
    ID string `gorm:"primaryKey"`
    AccountID string `gorm:"not null"`
    FIGI string `gorm:"not null"`
    Time time.Time `gorm:"not null"`
    Direction string `gorm:"not null"`
    Price float64 `gorm:"not null"`
    Quantity int `gorm:"not null"`
    Status string `gorm:"not null"`
    Commission float64
    Strategy string
    Reason string
    OperationID string
    TradeID string
    ExecutionTime time.Time
}

type Position struct {
    FIGI string `gorm:"primaryKey"`
    Quantity int `gorm:"not null"`
    AveragePrice float64 `gorm:"not null"`
    CurrentPrice float64 `gorm:"not null"`
    UnrealizedPnL float64 `gorm:"not null"`
    RealizedPnL float64 `gorm:"not null"`
    LastUpdate time.Time `gorm:"not null"`
}

type FIFOEntry struct {
    ID string `gorm:"primaryKey"`
    FIGI string `gorm:"not null"`
    Quantity int `gorm:"not null"`
    Price float64 `gorm:"not null"`
    Timestamp time.Time `gorm:"not null"`
    OrderID string `gorm:"not null"`
    Direction string `gorm:"not null"`
}

type Candle struct {
    ID int `gorm:"primaryKey;autoIncrement"`
    FIGI string `gorm:"not null"`
    Time time.Time `gorm:"not null"`
    Open float64 `gorm:"not null"`
    High float64 `gorm:"not null"`
    Low float64 `gorm:"not null"`
    Close float64 `gorm:"not null"`
    Volume int `gorm:"not null"`
}
```

## 🌐 Веб-интерфейс

### 1. WebServer структура
```go
type WebServer struct {
    router *gin.Engine
    hub *Hub
    dataManager *DataManager
    logger *logrus.Logger
}

func (w *WebServer) Start() error
func (w *WebServer) Stop() error
func (w *WebServer) SetupRoutes()
func (w *WebServer) HandleWebSocket(c *gin.Context)
```

### 2. WebSocket Hub
```go
type Hub struct {
    clients map[*Client]bool
    register chan *Client
    unregister chan *Client
    broadcast chan []byte
    mu sync.RWMutex
}

func (h *Hub) Run()
func (h *Hub) Register(client *Client)
func (h *Hub) Unregister(client *Client)
func (h *Hub) Broadcast(data []byte)
```

### 3. API endpoints
```go
// REST API
GET /api/portfolio
GET /api/positions
GET /api/orders
GET /api/candles
GET /api/market-status

// WebSocket
WS /ws
```

## 🚀 Развертывание

### 1. Docker
```dockerfile
FROM golang:1.21-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o trading-system cmd/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates
WORKDIR /root/
COPY --from=builder /app/trading-system .
CMD ["./trading-system"]
```

### 2. Docker Compose
```yaml
version: '3.8'
services:
  trading-system:
    build: .
    ports:
      - "8080:8080"
    environment:
      - TINKOFF_TOKEN=${TINKOFF_TOKEN}
      - TINKOFF_SANDBOX_TOKEN=${TINKOFF_SANDBOX_TOKEN}
      - TINKOFF_ACCOUNT_ID=${TINKOFF_ACCOUNT_ID}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

### 3. Systemd service
```ini
[Unit]
Description=Trading System
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/opt/trading-system
ExecStart=/opt/trading-system/trading-system
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 📝 Логирование

### 1. Logrus конфигурация
```go
func SetupLogging(config *LoggingConfig) *logrus.Logger {
    logger := logrus.New()
    
    if config.Level == "debug" {
        logger.SetLevel(logrus.DebugLevel)
    } else {
        logger.SetLevel(logrus.InfoLevel)
    }
    
    formatter := &logrus.TextFormatter{
        TimestampFormat: "2006-01-02 15:04:05",
        FullTimestamp: true,
    }
    logger.SetFormatter(formatter)
    
    if config.File != "" {
        file, err := os.OpenFile(config.File, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
        if err == nil {
            logger.SetOutput(file)
        }
    }
    
    return logger
}
```

### 2. Структурированное логирование
```go
logger.WithFields(logrus.Fields{
    "figi": figi,
    "price": price,
    "quantity": quantity,
    "direction": direction,
}).Info("Order executed")
```

## 🔄 Миграция данных

### 1. Миграция из Python
```go
func MigrateFromPython(pythonDBPath string) error {
    // Подключение к Python SQLite
    pythonDB, err := sql.Open("sqlite3", pythonDBPath)
    if err != nil {
        return err
    }
    defer pythonDB.Close()
    
    // Миграция ордеров
    if err := migrateOrders(pythonDB, goDB); err != nil {
        return err
    }
    
    // Миграция позиций
    if err := migratePositions(pythonDB, goDB); err != nil {
        return err
    }
    
    // Миграция FIFO
    if err := migrateFIFO(pythonDB, goDB); err != nil {
        return err
    }
    
    return nil
}
```

## 🎯 Критические сценарии

### 1. Торговый цикл
1. **Получение сигнала** → SignalManager
2. **Проверка рисков** → RiskManager
3. **Создание ордера** → OrderExecutor
4. **Исполнение ордера** → TinkoffAPI
5. **Обновление позиции** → PositionManager
6. **Синхронизация** → PositionSyncService

### 2. Обработка ошибок
- ✅ **API ошибки** - retry с exponential backoff
- ✅ **Сетевые ошибки** - переподключение
- ✅ **База данных** - транзакции и rollback
- ✅ **Критические ошибки** - graceful shutdown

### 3. Производительность
- ✅ **Goroutines** для параллельной обработки
- ✅ **Channels** для межкомпонентного взаимодействия
- ✅ **Connection pooling** для API
- ✅ **Кэширование** для часто используемых данных

## ❓ Вопросы для уточнения

1. **Приоритеты миграции** - с каких компонентов начать?
2. **Тестирование** - нужны ли дополнительные тесты?
3. **Конфигурация** - какие параметры критичны?
4. **Мониторинг** - какие метрики важны?
5. **Развертывание** - требования к production?

## 📚 Дополнительные ресурсы

- **Tinkoff Go SDK**: https://github.com/Tinkoff/invest-api-go-sdk
- **Gin Web Framework**: https://github.com/gin-gonic/gin
- **GORM ORM**: https://gorm.io/
- **Logrus Logging**: https://github.com/sirupsen/logrus
- **WebSocket**: https://github.com/gorilla/websocket
