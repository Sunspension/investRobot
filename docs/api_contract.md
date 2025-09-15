## API Contract (Protobuf) — investrobot.v1

Файл контракта: `api/investrobot/v1/contract.proto`

Включает сервисы и типы:
- VisualizationSink: OnCandle, OnSignal, OnMarketStatus
- MarketDataStream: Subscribe (stream Candle)
- StrategyEngine: bidirectional stream (Candle ↔ Signal)
- OrderExecutor: Execute(OrderIntent → OrderExecution)
- PortfolioManager: GetPortfolio / GetPosition
- RiskManager: CheckTradeRisk
- SignalDispatcher: Dispatch(Signal)

### Генерация кода

Примеры команд для генерации клиента/сервера:

Go (google.golang.org/protobuf + grpc):
```bash
protoc \
  -I . \
  --go_out=. --go_opt=paths=source_relative \
  --go-grpc_out=. --go-grpc_opt=paths=source_relative \
  api/investrobot/v1/contract.proto
```

Python (grpcio-tools):
```bash
python -m grpc_tools.protoc \
  -I . \
  --python_out=. \
  --grpc_python_out=. \
  api/investrobot/v1/contract.proto
```

TypeScript (ts-proto):
```bash
protoc \
  -I . \
  --ts_out=. \
  --ts_opt=esModuleInterop=true,env=node,outputServices=grpc-js \
  api/investrobot/v1/contract.proto
```

### Следующие шаги
- Определить схемы конфигураций и политики ретраев (опционально отдельный .proto)
- При необходимости — REST-шлюз (OpenAPI) для чтения портфеля/статуса


