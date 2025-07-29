#!/usr/bin/env python3
"""
Специализированный сервис-локатор для системы визуализации
"""
import logging
from typing import Optional, Dict, Any
from .interfaces import DependenciesProviderFactoryable, DependenciesProvidable
from .provider_factories import (
    StandardDependenciesProviderFactory,
    CachedDependenciesProviderFactory,
    TestDependenciesProviderFactory
)
from .factory_types import FactoryType
from robotlib.utils.logger import get_logger


class VisualizationServiceLocator:
    """Специализированный сервис-локатор для визуализации"""
    
    def __init__(self):
        self.logger = get_logger("visualization_service_locator")
        self._factories: Dict[FactoryType, DependenciesProviderFactoryable] = {}
        self._default_factory: Optional[DependenciesProviderFactoryable] = None
        self._register_default_factories()
    
    def _register_default_factories(self):
        """Регистрирует фабрики по умолчанию"""
        self.register_factory(FactoryType.STANDARD, StandardDependenciesProviderFactory())
        self.register_factory(FactoryType.CACHED, CachedDependenciesProviderFactory())
        self.register_factory(FactoryType.TEST, TestDependenciesProviderFactory())
        self.set_default_factory(FactoryType.STANDARD)
    
    def register_factory(self, factory_type: FactoryType, factory: DependenciesProviderFactoryable):
        """Регистрирует фабрику по типу"""
        self.logger.info(f"Регистрация фабрики: {factory_type.value} ({factory_type.get_display_name()})")
        self._factories[factory_type] = factory
    
    def get_factory(self, factory_type: FactoryType) -> Optional[DependenciesProviderFactoryable]:
        """Получает фабрику по типу"""
        factory = self._factories.get(factory_type)
        if factory:
            self.logger.debug(f"Получена фабрика: {factory_type.value}")
        else:
            self.logger.warning(f"Фабрика не найдена: {factory_type.value}")
        return factory
    
    def set_default_factory(self, factory_type: FactoryType):
        """Устанавливает фабрику по умолчанию"""
        factory = self.get_factory(factory_type)
        if factory:
            self._default_factory = factory
            self.logger.info(f"Установлена фабрика по умолчанию: {factory_type.value} ({factory_type.get_display_name()})")
        else:
            self.logger.error(f"Не удалось установить фабрику по умолчанию: {factory_type.value}")
    
    def get_default_factory(self) -> DependenciesProviderFactoryable:
        """Получает фабрику по умолчанию"""
        if self._default_factory is None:
            self.logger.error("Фабрика по умолчанию не установлена")
            raise RuntimeError("Фабрика по умолчанию не установлена")
        return self._default_factory
    
    def create_real_data_provider(self, config: Any, factory_type: Optional[FactoryType] = None) -> DependenciesProvidable:
        """Создает провайдер для реальных данных"""
        factory = self._get_factory(factory_type)
        return factory.create_real_data_provider(config)
    
    def create_mock_data_provider(self, factory_type: Optional[FactoryType] = None) -> DependenciesProvidable:
        """Создает провайдер для мок данных"""
        factory = self._get_factory(factory_type)
        return factory.create_mock_data_provider()
    
    def _get_factory(self, factory_type: Optional[FactoryType]) -> DependenciesProviderFactoryable:
        """Получает фабрику по типу или по умолчанию"""
        if factory_type:
            factory = self.get_factory(factory_type)
            if factory is None:
                self.logger.warning(f"Фабрика {factory_type.value} не найдена, используется фабрика по умолчанию")
                factory = self.get_default_factory()
        else:
            factory = self.get_default_factory()
        
        return factory
    
    def list_factories(self) -> Dict[str, str]:
        """Возвращает список зарегистрированных фабрик"""
        return {
            factory_type.value: factory.__class__.__name__ 
            for factory_type, factory in self._factories.items()
        }
    
    def list_factory_types(self) -> Dict[str, str]:
        """Возвращает список типов фабрик с описаниями"""
        return {
            factory_type.value: factory_type.get_display_name()
            for factory_type in self._factories.keys()
        }
    
    def clear_cache(self, factory_type: FactoryType = FactoryType.CACHED):
        """Очищает кэш для указанной фабрики"""
        factory = self.get_factory(factory_type)
        if factory and hasattr(factory, 'clear_cache'):
            factory.clear_cache()
            self.logger.info(f"Кэш очищен для фабрики: {factory_type.value} ({factory_type.get_display_name()})")
        else:
            self.logger.warning(f"Фабрика {factory_type.value} не поддерживает очистку кэша")


# Глобальный экземпляр сервис-локатора для визуализации
_visualization_service_locator = VisualizationServiceLocator()


def get_visualization_service_locator() -> VisualizationServiceLocator:
    """Получает глобальный экземпляр сервис-локатора для визуализации"""
    return _visualization_service_locator


def create_real_data_provider(config: Any, factory_type: Optional[FactoryType] = None) -> DependenciesProvidable:
    """Создает провайдер для реальных данных через сервис-локатор"""
    return _visualization_service_locator.create_real_data_provider(config, factory_type)


def create_mock_data_provider(factory_type: Optional[FactoryType] = None) -> DependenciesProvidable:
    """Создает провайдер для мок данных через сервис-локатор"""
    return _visualization_service_locator.create_mock_data_provider(factory_type)
