# 🎭 Централизованная папка моков

Все моки для тестирования собраны в одном месте. Каждый мок в отдельном файле для удобства навигации и поддержки.

## 📁 Структура файлов

### API клиенты
- **`api_client_mock.py`** - `MockAPIClient` - простой мок API клиента для исторических тестов
- **`tinkoff_api_client_mock.py`** - `MockTinkoffAPIClient` - полная реализация интерфейса Tinkoff API

### Менеджеры
- **`portfolio_manager_mock.py`** - `MockPortfolioManager` - мок менеджера портфеля
- **`risk_manager_mock.py`** - `MockRiskManager` - мок менеджера рисков
- **`signal_manager_mock.py`** - `MockSignalManager` - мок менеджера сигналов

### Исполнители
- **`order_executor_mock.py`** - `MockOrderExecutor` - мок исполнителя ордеров для исторических данных

### Потоки данных
- **`market_data_stream_mock.py`** - `MockMarketDataStream` - мок потока рыночных данных

### Сессии
- **`session_mocks.py`** - моки для компонентов торговой сессии:
  - `MockSessionStats` - статистика сессии
  - `MockSessionInitializer` - инициализатор сессии
  - `MockSessionController` - контроллер сессии
  - `MockTradingSession` - торговая сессия

### Зависимости
- **`strategy_dependencies_mock.py`** - `MockStrategyDependencies` - мок всех зависимостей стратегии

## 🚀 Использование

### Импорт всех моков
```python
from tests.mocks import MockAPIClient, MockOrderExecutor, MockPortfolioManager
```

### Импорт конкретного мока
```python
from tests.mocks.api_client_mock import MockAPIClient
from tests.mocks.order_executor_mock import MockOrderExecutor
```

### Импорт моков сессий
```python
from tests.mocks import MockTradingSession, MockSessionController
```

## 📋 Принципы

1. **Один мок - один файл** - каждый мок в отдельном файле
2. **Понятные имена** - имена файлов отражают назначение мока
3. **Централизованный экспорт** - все моки доступны через `__init__.py`
4. **Документация** - каждый мок имеет docstring с описанием
5. **Консистентность** - все моки следуют единому стилю

## 🔍 Поиск моков

Перед созданием нового мока всегда проверяйте:
1. Есть ли уже похожий мок в этой папке?
2. Можно ли расширить существующий мок?
3. Нужен ли отдельный файл или можно добавить в существующий?

## 📝 Добавление новых моков

1. Создайте новый файл `{название}_mock.py`
2. Добавьте импорт в `__init__.py`
3. Добавьте в `__all__` список
4. Обновите этот README
