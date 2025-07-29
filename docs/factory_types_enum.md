# Перечисление FactoryType

## 🎯 Обзор

`FactoryType` - это перечисление (Enum) для типов фабрик провайдеров зависимостей в ServiceLocator.

## 🏗️ Структура

```python
class FactoryType(Enum):
    # Стандартные фабрики
    STANDARD = "standard"
    CACHED = "cached"
    TEST = "test"
    
    # Кастомные фабрики
    CUSTOM = "custom"
    MOCK = "mock"
    PRODUCTION = "production"
    DEVELOPMENT = "development"
```

## 🔧 Основные методы

### Получение типов
```python
# Все типы
all_types = FactoryType.get_all_types()

# Стандартные типы
standard_types = FactoryType.get_standard_types()

# Кастомные типы
custom_types = FactoryType.get_custom_types()

# Тип по умолчанию
default_type = FactoryType.get_default()
```

### Проверка типов
```python
# Проверка на стандартный тип
is_standard = FactoryType.STANDARD.is_standard()  # True

# Проверка на кастомный тип
is_custom = FactoryType.CUSTOM.is_custom()  # True
```

### Отображение
```python
# Строковое представление
str(FactoryType.STANDARD)  # "standard"

# Отображаемое имя
FactoryType.STANDARD.get_display_name()  # "Стандартная фабрика"

# Описание
FactoryType.STANDARD.get_description()  # "Создает новые экземпляры..."
```

## 🚀 Использование в ServiceLocator

### Базовое использование
```python
from visualization import FactoryType, get_service_locator

locator = get_service_locator()

# Создание провайдеров с перечислением
mock_provider = locator.create_mock_data_provider(FactoryType.STANDARD)
real_provider = locator.create_real_data_provider(config, FactoryType.CACHED)
test_provider = locator.create_real_data_provider({"api_key": "test"}, FactoryType.TEST)
```

### Регистрация фабрик
```python
# Регистрация с перечислением
locator.register_factory(FactoryType.CUSTOM, CustomFactory())

# Использование зарегистрированной фабрики
provider = locator.create_mock_data_provider(FactoryType.CUSTOM)
```

### Переключение фабрик
```python
# Установка фабрики по умолчанию
locator.set_default_factory(FactoryType.CACHED)

# Теперь все вызовы без указания типа будут использовать CACHED
provider = locator.create_mock_data_provider()  # использует CACHED
```

## 📝 Примеры использования

### Создание провайдеров
```python
from visualization import FactoryType, get_service_locator

locator = get_service_locator()

# Разные типы фабрик
providers = {
    FactoryType.STANDARD: locator.create_mock_data_provider(FactoryType.STANDARD),
    FactoryType.CACHED: locator.create_mock_data_provider(FactoryType.CACHED),
    FactoryType.TEST: locator.create_mock_data_provider(FactoryType.TEST)
}

# Проверка кэширования
print(f"Кэширование работает: {providers[FactoryType.CACHED] is providers[FactoryType.CACHED]}")
```

### Регистрация кастомных фабрик
```python
class CustomFactory(DependenciesProviderFactoryInterface):
    def create_mock_data_provider(self):
        return CustomProvider()

# Регистрация
locator.register_factory(FactoryType.CUSTOM, CustomFactory())

# Использование
provider = locator.create_mock_data_provider(FactoryType.CUSTOM)
```

### Переключение окружений
```python
# Для разработки
locator.set_default_factory(FactoryType.DEVELOPMENT)

# Для тестирования
locator.set_default_factory(FactoryType.TEST)

# Для продакшна
locator.set_default_factory(FactoryType.PRODUCTION)
```

### Обработка ошибок
```python
# IDE покажет ошибку для несуществующих значений
# provider = locator.create_mock_data_provider(FactoryType.INVALID)  # Ошибка типизации!

# Правильный способ - используйте существующие значения
provider = locator.create_mock_data_provider(FactoryType.STANDARD)
```

## 🎉 Заключение

`FactoryType` делает работу с ServiceLocator более безопасной и удобной:

- **Типобезопасность** - ошибки ловятся на этапе разработки
- **Автодополнение** - IDE подсказывает доступные варианты
- **Читаемость** - код становится более понятным
- **Валидация** - автоматическая проверка корректности типов
- **Строгая типизация** - только перечисления, никаких строк

Использование перечисления - это современный, профессиональный подход к разработке! 🚀
