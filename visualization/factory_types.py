#!/usr/bin/env python3
"""
Типы фабрик для ServiceLocator
"""
from enum import Enum, auto


class FactoryType(Enum):
    """Типы фабрик провайдеров зависимостей"""
    
    # Стандартные фабрики
    STANDARD = "standard"
    CACHED = "cached"
    TEST = "test"
    
    # Кастомные фабрики (для расширения)
    CUSTOM = "custom"
    MOCK = "mock"
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    
    def __str__(self) -> str:
        """Возвращает строковое представление типа фабрики"""
        return self.value
    
    @classmethod
    def get_default(cls) -> 'FactoryType':
        """Возвращает тип фабрики по умолчанию"""
        return cls.STANDARD
    
    @classmethod
    def get_cached(cls) -> 'FactoryType':
        """Возвращает тип кэшированной фабрики"""
        return cls.CACHED
    
    @classmethod
    def get_test(cls) -> 'FactoryType':
        """Возвращает тип тестовой фабрики"""
        return cls.TEST
    
    @classmethod
    def get_all_types(cls) -> list['FactoryType']:
        """Возвращает все доступные типы фабрик"""
        return [factory_type for factory_type in cls]
    
    @classmethod
    def get_standard_types(cls) -> list['FactoryType']:
        """Возвращает только стандартные типы фабрик"""
        return [cls.STANDARD, cls.CACHED, cls.TEST]
    
    @classmethod
    def get_custom_types(cls) -> list['FactoryType']:
        """Возвращает только кастомные типы фабрик"""
        return [cls.CUSTOM, cls.MOCK, cls.PRODUCTION, cls.DEVELOPMENT]
    
    def is_standard(self) -> bool:
        """Проверяет, является ли тип стандартным"""
        return self in self.get_standard_types()
    
    def is_custom(self) -> bool:
        """Проверяет, является ли тип кастомным"""
        return self in self.get_custom_types()
    
    def get_display_name(self) -> str:
        """Возвращает отображаемое имя типа фабрики"""
        display_names = {
            self.STANDARD: "Стандартная фабрика",
            self.CACHED: "Кэшированная фабрика",
            self.TEST: "Тестовая фабрика",
            self.CUSTOM: "Кастомная фабрика",
            self.MOCK: "Мок фабрика",
            self.PRODUCTION: "Продакшн фабрика",
            self.DEVELOPMENT: "Фабрика разработки"
        }
        return display_names.get(self, f"Неизвестная фабрика ({self.value})")
    
    def get_description(self) -> str:
        """Возвращает описание типа фабрики"""
        descriptions = {
            self.STANDARD: "Создает новые экземпляры провайдеров при каждом вызове",
            self.CACHED: "Кэширует созданные провайдеры для оптимизации производительности",
            self.TEST: "Создает провайдеры для тестирования с мок данными",
            self.CUSTOM: "Пользовательская фабрика для специфических нужд",
            self.MOCK: "Фабрика для создания мок объектов в тестах",
            self.PRODUCTION: "Фабрика для продакшн окружения",
            self.DEVELOPMENT: "Фабрика для окружения разработки"
        }
        return descriptions.get(self, "Описание недоступно")
