# Архитектура с инверсией зависимостей

## 🎯 Обзор

Система визуализации использует принципы инверсии зависимостей (Dependency Inversion Principle) для создания гибкой, тестируемой и расширяемой архитектуры.

## 🏗️ Архитектурные принципы

### 1. Инверсия зависимостей (DIP)
- Высокоуровневые модули не зависят от низкоуровневых
- Оба зависят от абстракций (интерфейсы)
- Абстракции не зависят от деталей

### 2. Принцип единственной ответственности (SRP)
- Каждый класс решает одну задачу
- Фабрики только создают объекты
- Провайдеры только предоставляют зависимости

### 3. Принцип открытости/закрытости (OCP)
- Код открыт для расширения (новые фабрики)
- Закрыт для модификации (существующие интерфейсы)

## 📁 Структура модулей

```
visualization/
├── interfaces.py              # Интерфейсы и абстракции
├── factories.py               # Фабрики для создания компонентов
├── provider_factories.py      # Фабрики для создания провайдеров
├── service_locator.py         # Сервис-локатор для управления фабриками
├── dependencies_provider.py   # Реализация провайдеров зависимостей
└── trading_session_manager.py # Менеджер с инжекцией зависимостей
```

## 🔌 Интерфейсы

### TradingSessionManagerInterface
```python
class TradingSessionManagerInterface(ABC):
    @abstractmethod
    def get_trading_session(self) -> Any:
        """Возвращает TradingSession"""
        pass
    
    @abstractmethod
    def get_signal_manager(self) -> Any:
        """Возвращает SignalManager"""
        pass
    
    @abstractmethod
    def get_trading_config(self) -> TradingConfig:
        """Возвращает конфигурацию торговли"""
        pass
```

### DependenciesProvider
```python
class DependenciesProvider(ABC):
    @abstractmethod
    def get_trading_session_factory(self) -> TradingSessionFactory:
        """Возвращает фабрику TradingSession"""
        pass
    
    @abstractmethod
    def get_strategy_manager_factory(self) -> StrategyManagerFactory:
        """Возвращает фабрику StrategyManager"""
        pass
```

## 🏭 Фабрики

### TradingSessionFactory
Создает экземпляры TradingSession:

- **RealTradingSessionFactory** - для реальных данных
- **MockTradingSessionFactory** - для мок данных

### StrategyManagerFactory
Создает экземпляры StrategyManager:

- **RealStrategyManagerFactory** - для реальных данных
- **MockStrategyManagerFactory** - для мок данных

### DependenciesProviderFactory
Создает провайдеры зависимостей:

- **StandardDependenciesProviderFactory** - стандартная фабрика
- **CachedDependenciesProviderFactory** - с кэшированием
- **TestDependenciesProviderFactory** - для тестирования

## 🔧 ServiceLocator

Центральный компонент для управления фабриками:

```python
# Получение глобального сервис-локатора
locator = get_service_locator()

# Регистрация кастомной фабрики
locator.register_factory(FactoryType.CUSTOM, CustomFactory())

# Создание провайдеров
provider = locator.create_mock_data_provider(FactoryType.CUSTOM)

# Переключение фабрики по умолчанию
locator.set_default_factory(FactoryType.CACHED)
```

## 🚀 Использование

### Базовое использование

```python
from visualization import (
    get_trading_session_manager_class,
    create_mock_data_provider,
    create_real_data_provider
)

# Создание с мок данными
provider = create_mock_data_provider()
TradingSessionManager = get_trading_session_manager_class()
manager = TradingSessionManager(strategy_params, provider)

# Создание с реальными данными
provider = create_real_data_provider(config)
manager = TradingSessionManager(strategy_params, provider)
```

### Расширенное использование

```python
from visualization import ServiceLocator, get_service_locator

# Получение сервис-локатора
locator = get_service_locator()

# Регистрация кастомной фабрики
class CustomFactory(DependenciesProviderFactoryInterface):
    def create_mock_data_provider(self):
        return CustomProvider()

locator.register_factory(FactoryType.CUSTOM, CustomFactory())

# Использование кастомной фабрики
provider = locator.create_mock_data_provider(FactoryType.CUSTOM)
TradingSessionManager = get_trading_session_manager_class()
manager = TradingSessionManager(strategy_params, provider)
```

### Тестирование

```python
from visualization import TestDependenciesProviderFactory

# Создание тестовой фабрики с мок провайдером
mock_provider = MockDependenciesProvider()
test_factory = TestDependenciesProviderFactory(mock_provider)

# Регистрация в сервис-локаторе
locator.register_factory(FactoryType.TEST, test_factory)

# Использование в тестах
provider = locator.create_mock_data_provider(FactoryType.TEST)
TradingSessionManager = get_trading_session_manager_class()
manager = TradingSessionManager(strategy_params, provider)
```

## 🎯 Преимущества

### 1. Тестируемость
- Легко подставлять моки
- Изолированное тестирование компонентов
- Контролируемые зависимости

### 2. Гибкость
- Легко переключаться между реализациями
- Динамическое изменение поведения
- Конфигурируемые фабрики

### 3. Расширяемость
- Легко добавлять новые типы фабрик
- Плагинная архитектура
- Минимальные изменения существующего кода

### 4. Слабая связанность
- Компоненты не зависят друг от друга напрямую
- Зависимости инжектируются извне
- Легко заменять реализации

### 5. Высокая когезия
- Каждый класс решает одну задачу
- Четкое разделение ответственности
- Понятная структура кода

## 🔄 Миграция

### Старый код (deprecated)
```python
# ❌ Старый способ
from visualization import DependenciesProviderFactory

provider = DependenciesProviderFactory.create_mock_data_provider()
TradingSessionManager = get_trading_session_manager_class()
manager = TradingSessionManager(strategy_params, provider)
```

### Новый код
```python
# ✅ Новый способ
from visualization import create_mock_data_provider

provider = create_mock_data_provider()
TradingSessionManager = get_trading_session_manager_class()
manager = TradingSessionManager(strategy_params, provider)
```

## 📝 Лучшие практики

1. **Используйте интерфейсы** - программируйте против абстракций, а не конкретных реализаций
2. **Инжектируйте зависимости** - не создавайте их внутри классов
3. **Используйте ServiceLocator** - для централизованного управления фабриками
4. **Регистрируйте фабрики** - для расширения функциональности
5. **Тестируйте с моками** - используйте TestDependenciesProviderFactory

## 🎉 Заключение

Архитектура с инверсией зависимостей делает систему:
- **Более тестируемой** - легко подставлять моки
- **Более гибкой** - легко менять реализации
- **Более расширяемой** - легко добавлять новую функциональность
- **Более поддерживаемой** - четкое разделение ответственности

Это современный, профессиональный подход к разработке, который следует принципам SOLID и обеспечивает высокое качество кода.
