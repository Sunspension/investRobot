#!/usr/bin/env python3
"""
Фабрики для создания провайдеров зависимостей
"""
import logging
from typing import Any, Optional
from .interfaces import DependenciesProviderFactoryable, DependenciesProvidable
from .dependencies_provider import VisualizationDependenciesProvider
from robotlib.utils.logger import get_logger


class StandardDependenciesProviderFactory(DependenciesProviderFactoryable):
    """Стандартная фабрика провайдеров зависимостей"""
    
    def __init__(self):
        self.logger = get_logger("standard_factory")
    
    def create_real_data_provider(self, config: Any) -> DependenciesProvidable:
        """Создает провайдер для реальных данных"""
        self.logger.info("Создание провайдера для реальных данных")
        return VisualizationDependenciesProvider(config, use_real_data=True)
    
    def create_mock_data_provider(self) -> DependenciesProvidable:
        """Создает провайдер для мок данных"""
        self.logger.info("Создание провайдера для мок данных")
        return VisualizationDependenciesProvider(use_real_data=False)
    


class CachedDependenciesProviderFactory(DependenciesProviderFactoryable):
    """Фабрика провайдеров зависимостей с кэшированием"""
    
    def __init__(self):
        self.logger = get_logger("cached_factory")
        self._cached_providers = {}
    
    def create_real_data_provider(self, config: Any) -> DependenciesProvidable:
        """Создает провайдер для реальных данных с кэшированием"""
        cache_key = f"real_{id(config)}"
        
        if cache_key not in self._cached_providers:
            self.logger.info("Создание нового провайдера для реальных данных")
            self._cached_providers[cache_key] = VisualizationDependenciesProvider(config, use_real_data=True)
        else:
            self.logger.info("Использование кэшированного провайдера для реальных данных")
        
        return self._cached_providers[cache_key]
    
    def create_mock_data_provider(self) -> DependenciesProvidable:
        """Создает провайдер для мок данных с кэшированием"""
        cache_key = "mock"
        
        if cache_key not in self._cached_providers:
            self.logger.info("Создание нового провайдера для мок данных")
            self._cached_providers[cache_key] = VisualizationDependenciesProvider(use_real_data=False)
        else:
            self.logger.info("Использование кэшированного провайдера для мок данных")
        
        return self._cached_providers[cache_key]
    
    
    def clear_cache(self):
        """Очищает кэш провайдеров"""
        self.logger.info("Очистка кэша провайдеров")
        self._cached_providers.clear()


class TestDependenciesProviderFactory(DependenciesProviderFactoryable):
    """Фабрика провайдеров зависимостей для тестирования"""
    
    def __init__(self, mock_provider: Optional[DependenciesProvidable] = None):
        self.logger = get_logger("test_factory")
        self.mock_provider = mock_provider
    
    def create_real_data_provider(self, config: Any) -> DependenciesProvidable:
        """Создает провайдер для реальных данных (в тестах может быть мок)"""
        if self.mock_provider:
            self.logger.info("Использование мок провайдера для тестирования")
            return self.mock_provider
        
        self.logger.info("Создание провайдера для реальных данных в тестах")
        return VisualizationDependenciesProvider(config, use_real_data=True)
    
    def create_mock_data_provider(self) -> DependenciesProvidable:
        """Создает провайдер для мок данных"""
        if self.mock_provider:
            self.logger.info("Использование мок провайдера для тестирования")
            return self.mock_provider
        
        self.logger.info("Создание провайдера для мок данных в тестах")
        return VisualizationDependenciesProvider(use_real_data=False)
    
