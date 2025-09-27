# Инверсия зависимостей: Реализация для PositionManager

## 🎯 **Проблема: Нарушение принципа инверсии зависимостей**

### **❌ Что было неправильно:**
```python
class PositionManager:
    def __init__(self, db_path: str, api_client: TinkoffAPIClient, risk_manager):
        # ... другие поля ...
        self._restoration_service = PositionRestorationService(api_client)  # ❌ Прямое создание!
```

**Проблемы:**
- ❌ **Жесткая связанность** - PositionManager напрямую зависит от конкретной реализации
- ❌ **Сложность тестирования** - нельзя легко подменить сервис моком
- ❌ **Нарушение SOLID** - нарушается принцип инверсии зависимостей

## ✅ **Решение: Инверсия зависимостей**

### **1. Создание интерфейса:**
```python
# position_restoration_interface.py
class PositionRestorationServiceable(ABC):
    @abstractmethod
    async def restore_fifo_from_api(
        self, 
        api_positions: Dict[str, Position],
        existing_fifo: Dict[str, List[FIFOEntry]],
        days_back: int = 30
    ) -> Dict[str, List[FIFOEntry]]:
        pass
    
    @abstractmethod
    async def validate_restored_fifo(
        self, 
        fifo_data: Dict[str, List[FIFOEntry]]
    ) -> Dict[str, bool]:
        pass
```

### **2. Обновление PositionManager:**
```python
class PositionManager:
    def __init__(
        self, 
        db_path: str, 
        api_client: TinkoffAPIClient, 
        risk_manager,
        restoration_service: PositionRestorationServiceable  # ✅ Интерфейс!
    ):
        # ... другие поля ...
        self._restoration_service = restoration_service  # ✅ Инъекция зависимости!
```

### **3. Обновление фабрики:**
```python
class PositionManagerFactory:
    @staticmethod
    def create_position_manager(
        db_path: str, 
        api_client: TinkoffAPIClient,
        risk_manager,
        restoration_service: PositionRestorationServiceable  # ✅ Интерфейс!
    ) -> PositionManager:
        return PositionManager(db_path, api_client, risk_manager, restoration_service)
```

### **4. Обновление DI контейнера:**
```python
class TradingSystemContainer:
    async def get_restoration_service(self):
        """Получает сервис восстановления позиций"""
        if 'restoration_service' not in self._instances:
            from robotlib.trading.position_restoration_service import PositionRestorationService
            api_client = await self.get_api_client()
            self._instances['restoration_service'] = PositionRestorationService(api_client)
        return self._instances['restoration_service']
    
    async def get_position_manager(self) -> PositionManager:
        # ... получение других зависимостей ...
        restoration_service = await self.get_restoration_service()  # ✅ Инъекция!
        return await PositionManagerFactory.create_and_sync_position_manager(
            db_path=self._config.positions_db_path,
            api_client=api_client,
            risk_manager=risk_manager,
            restoration_service=restoration_service
        )
```

## 🧪 **Тестирование инверсии зависимостей**

### **✅ Результаты тестирования:**

#### **Тест 1: Сервис не вызывался при создании**
```
restore_called: False
validate_called: False
```

#### **Тест 2: Симуляция восстановления FIFO**
```
Восстановлено FIFO для 1 FIGI
restore_called: True
```

#### **Тест 3: Валидация FIFO**
```
Результаты валидации: {'FUTIMOEXF000': True}
validate_called: True
```

#### **Тест 4: Замена сервиса**
```
✅ PositionManager создан с другим сервисом
Новый сервис - FIFO: {'FUTIMOEXF000': []}
Новый сервис - валидация: {'FUTIMOEXF000': False}
```

## 🎯 **Преимущества инверсии зависимостей**

### **1. Тестируемость:**
- ✅ **Легкое мокирование** - можно подставить любой сервис
- ✅ **Изолированное тестирование** - тестируем PositionManager отдельно
- ✅ **Контролируемые тесты** - полный контроль над поведением зависимостей

### **2. Гибкость:**
- ✅ **Замена реализации** - можно легко заменить сервис
- ✅ **Разные стратегии** - разные сервисы для разных сценариев
- ✅ **Конфигурируемость** - выбор сервиса через конфигурацию

### **3. Соблюдение SOLID:**
- ✅ **Dependency Inversion Principle** - зависимость от абстракций, не от конкретных классов
- ✅ **Open/Closed Principle** - открыт для расширения, закрыт для модификации
- ✅ **Interface Segregation** - четкие интерфейсы для каждого сервиса

### **4. Поддерживаемость:**
- ✅ **Слабая связанность** - компоненты независимы друг от друга
- ✅ **Легкое добавление** новых реализаций
- ✅ **Простое рефакторинг** - изменения в одном компоненте не влияют на другие

## 🔧 **Архитектура компонентов**

### **Интерфейс:**
```python
PositionRestorationServiceable (ABC)
├── restore_fifo_from_api()
└── validate_restored_fifo()
```

### **Реализация:**
```python
PositionRestorationService (PositionRestorationServiceable)
├── restore_fifo_from_api() → Dict[str, List[FIFOEntry]]
└── validate_restored_fifo() → Dict[str, bool]
```

### **Использование:**
```python
PositionManager
├── _restoration_service: PositionRestorationServiceable
├── sync_on_startup() → использует сервис
└── другие методы → используют сервис
```

## 🚀 **Практические примеры использования**

### **1. Тестирование с мок-сервисом:**
```python
class MockRestorationService(PositionRestorationServiceable):
    async def restore_fifo_from_api(self, api_positions, existing_fifo, days_back=30):
        return {"FUTIMOEXF000": [mock_fifo_entry]}
    
    async def validate_restored_fifo(self, fifo_data):
        return {"FUTIMOEXF000": True}

# Использование в тестах
position_manager = PositionManager(
    db_path='test.db',
    api_client=mock_api,
    risk_manager=mock_risk,
    restoration_service=MockRestorationService()  # ✅ Мок-сервис!
)
```

### **2. Замена сервиса в продакшене:**
```python
class FastRestorationService(PositionRestorationServiceable):
    """Быстрый сервис для продакшена"""
    async def restore_fifo_from_api(self, api_positions, existing_fifo, days_back=30):
        # Оптимизированная реализация
        pass

# Использование в продакшене
position_manager = PositionManager(
    db_path='prod.db',
    api_client=prod_api,
    risk_manager=prod_risk,
    restoration_service=FastRestorationService()  # ✅ Продакшен-сервис!
)
```

### **3. Конфигурируемый сервис:**
```python
def create_restoration_service(config: Config) -> PositionRestorationServiceable:
    if config.environment == 'test':
        return MockRestorationService()
    elif config.environment == 'production':
        return FastRestorationService()
    else:
        return PositionRestorationService(api_client)
```

## 🎯 **Заключение**

### **✅ Инверсия зависимостей успешно реализована!**

**Теперь система имеет:**
- ✅ **Четкие интерфейсы** для всех сервисов
- ✅ **Слабое связывание** между компонентами
- ✅ **Легкое тестирование** с мок-объектами
- ✅ **Гибкую архитектуру** для будущих изменений
- ✅ **Соблюдение SOLID** принципов

**Это обеспечивает масштабируемую, тестируемую и поддерживаемую архитектуру!**

---

*Инверсия зависимостей реализована: 2025-01-27*
