# КРИТИЧЕСКИЕ ПРАВИЛА РАЗРАБОТКИ

## 1. ОБЯЗАТЕЛЬНОЕ ИСПОЛЬЗОВАНИЕ ЯВНЫХ ТИПОВ

**ПРАВИЛО**: В проекте обязательно использовать явные типы (type hints) для всех параметров функций, возвращаемых значений, переменных классов и методов.

### Что должно быть типизировано:
- ✅ Все параметры функций и методов
- ✅ Все возвращаемые значения (return type)
- ✅ Все атрибуты классов
- ✅ Все переменные в конструкторах
- ✅ Все параметры в интерфейсах/протоколах

### Примеры правильной типизации:

```python
# ✅ ПРАВИЛЬНО - явные типы
def __init__(self, figi: str, position_sizing_service: PositionSizingService) -> None:
    self._figi: str = figi
    self._position_sizing_service: PositionSizingService = position_sizing_service

async def execute(self, signal: Signal, position_context: PositionContext) -> List[OrderIntent]:
    orders: List[OrderIntent] = []
    return orders

# ❌ НЕПРАВИЛЬНО - без типов
def __init__(self, figi, position_sizing_service):
    self._figi = figi
    self._position_sizing_service = position_sizing_service

async def execute(self, signal, position_context):
    orders = []
    return orders
```

### Используемые типы:
- `str`, `int`, `float`, `bool` - базовые типы
- `List[Type]`, `Dict[str, Type]` - коллекции
- `Optional[Type]` - может быть None
- `Union[Type1, Type2]` - один из типов
- `AsyncMock`, `Mock` - для тестов
- Кастомные классы и интерфейсы

### Импорты для типизации:
```python
from typing import List, Dict, Optional, Union, Any
from unittest.mock import Mock, AsyncMock
```

## 2. ПРИНЦИПЫ ЗАВИСИМОСТЕЙ

**ПРАВИЛО**: Объекты не должны создаваться внутри классов, а должны передаваться как зависимости.

### Что НЕ делать:
```python
# ❌ НЕПРАВИЛЬНО - создание внутри класса
class Strategy:
    def __init__(self):
        self._logger = get_logger(__name__)  # Создание внутри
        self._api_client = TinkoffAPIClient()  # Создание внутри
```

### Что делать:
```python
# ✅ ПРАВИЛЬНО - передача как зависимости
class Strategy:
    def __init__(self, logger: Logger, api_client: TinkoffAPIClient) -> None:
        self._logger: Logger = logger
        self._api_client: TinkoffAPIClient = api_client
```

## 3. ПРОВЕРКА ПЕРЕД ИЗМЕНЕНИЯМИ

**ПРАВИЛО**: Перед внесением изменений всегда объяснять план и получать подтверждение.

### Процесс:
1. **Объяснить идею** - что и зачем изменяется
2. **Получить подтверждение** - дождаться одобрения
3. **Внести изменения** - только после подтверждения
4. **Проверить тесты** - убедиться что ничего не сломалось

## 4. УПРАВЛЕНИЕ ИМПОРТАМИ

**ПРАВИЛО**: Все импорты должны быть на уровне модуля в начале файла, неиспользуемые импорты должны быть удалены.

### Структура импортов:
```python
# 1. Стандартная библиотека
import asyncio
from typing import List, Optional

# 2. Сторонние библиотеки  
from unittest.mock import Mock, AsyncMock

# 3. Внутренние модули
from robotlib.utils.logger import get_logger
from robotlib.trading.order_types import OrderIntent
```

## 5. ТЕСТИРОВАНИЕ

**ПРАВИЛО**: Все изменения должны сопровождаться соответствующими тестами.

### Принципы:
- ✅ Использовать моки вместо реальных компонентов
- ✅ Тестировать как успешные, так и ошибочные сценарии
- ✅ Обновлять тесты при изменении архитектуры
- ✅ Удалять устаревшие тесты

## 6. АРХИТЕКТУРНЫЕ ПРИНЦИПЫ

**ПРАВИЛО**: Следовать принципам SOLID и чистой архитектуры.

### Принципы:
- **Single Responsibility** - один класс, одна ответственность
- **Open/Closed** - открыт для расширения, закрыт для модификации
- **Dependency Inversion** - зависимость от абстракций, не от конкретных классов
- **Interface Segregation** - интерфейсы должны быть специфичными
- **Liskov Substitution** - подклассы должны заменять базовые классы

---

**ВАЖНО**: Эти правила критичны для поддержания качества кода и архитектуры проекта. Нарушение этих правил может привести к проблемам в продакшене.