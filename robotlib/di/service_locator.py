#!/usr/bin/env python3
"""
Общий сервис-локатор для управления зависимостями
"""
import logging
from typing import Optional, Dict, Any, Type
from .interfaces import ServiceLocatable, Factoryable
from robotlib.utils.logger import get_logger


class ServiceLocator(ServiceLocatable):
    """Общий сервис-локатор для управления зависимостями"""
    
    def __init__(self):
        self.logger = get_logger("service_locator")
        self._factories: Dict[Type, Factoryable] = {}
        self._instances: Dict[Type, Any] = {}
    
    def register(self, service_type: Type, factory: Factoryable) -> None:
        """Регистрирует фабрику для типа сервиса"""
        self.logger.info(f"Регистрация фабрики для {service_type.__name__}")
        self._factories[service_type] = factory
    
    def register_instance(self, service_type: Type, instance: Any) -> None:
        """Регистрирует готовый экземпляр сервиса"""
        self.logger.info(f"Регистрация экземпляра для {service_type.__name__}")
        self._instances[service_type] = instance
    
    def get(self, service_type: Type) -> Any:
        """Получает экземпляр сервиса по типу"""
        # Сначала проверяем готовые экземпляры
        if service_type in self._instances:
            self.logger.debug(f"Получен готовый экземпляр {service_type.__name__}")
            return self._instances[service_type]
        
        # Затем создаем через фабрику
        factory = self._factories.get(service_type)
        if factory:
            self.logger.debug(f"Создание экземпляра {service_type.__name__} через фабрику")
            return factory.create()
        
        self.logger.error(f"Сервис {service_type.__name__} не зарегистрирован")
        raise RuntimeError(f"Сервис {service_type.__name__} не зарегистрирован")
    
    def get_factory(self, service_type: Type) -> Factoryable:
        """Получает фабрику для типа сервиса"""
        factory = self._factories.get(service_type)
        if not factory:
            self.logger.error(f"Фабрика для {service_type.__name__} не зарегистрирована")
            raise RuntimeError(f"Фабрика для {service_type.__name__} не зарегистрирована")
        return factory
    
    def is_registered(self, service_type: Type) -> bool:
        """Проверяет, зарегистрирован ли сервис"""
        return service_type in self._factories or service_type in self._instances
    
    def list_services(self) -> Dict[str, str]:
        """Возвращает список зарегистрированных сервисов"""
        result = {}
        
        # Добавляем фабрики
        for service_type, factory in self._factories.items():
            result[service_type.__name__] = f"Factory: {factory.__class__.__name__}"
        
        # Добавляем готовые экземпляры
        for service_type, instance in self._instances.items():
            result[service_type.__name__] = f"Instance: {instance.__class__.__name__}"
        
        return result
    
    def clear(self) -> None:
        """Очищает все зарегистрированные сервисы"""
        self.logger.info("Очистка всех зарегистрированных сервисов")
        self._factories.clear()
        self._instances.clear()


# Глобальный экземпляр сервис-локатора
_service_locator = ServiceLocator()


def get_service_locator() -> ServiceLocator:
    """Получает глобальный экземпляр сервис-локатора"""
    return _service_locator
