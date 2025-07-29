"""
Модуль для управления зависимостями (Dependency Injection)
"""
from .service_locator import ServiceLocator, get_service_locator
from .interfaces import ServiceLocatable, Factoryable

__all__ = [
    'ServiceLocator',
    'get_service_locator', 
    'ServiceLocatable',
    'Factoryable'
]
