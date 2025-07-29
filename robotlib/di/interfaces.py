"""
Общие интерфейсы для системы управления зависимостями
"""
from abc import ABC, abstractmethod
from typing import Any, TypeVar, Generic

T = TypeVar('T')


class Factoryable(ABC, Generic[T]):
    """Базовый интерфейс для фабрик"""
    
    @abstractmethod
    def create(self, *args, **kwargs) -> T:
        """Создает экземпляр типа T"""
        pass


class ServiceLocatable(ABC):
    """Интерфейс для сервис-локатора"""
    
    @abstractmethod
    def register(self, service_type: type, factory: Factoryable) -> None:
        """Регистрирует фабрику для типа сервиса"""
        pass
    
    @abstractmethod
    def get(self, service_type: type) -> Any:
        """Получает экземпляр сервиса по типу"""
        pass
    
    @abstractmethod
    def get_factory(self, service_type: type) -> Factoryable:
        """Получает фабрику для типа сервиса"""
        pass
