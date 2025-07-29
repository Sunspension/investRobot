#!/usr/bin/env python3
"""
Пакет визуализации торговых сигналов
Содержит модули для управления данными, построения графиков и UI
"""


# Прямые импорты для интерфейсов (без внешних зависимостей)
from .interfaces import (
    DependenciesProvidable,
    DependenciesProviderFactoryable
)
from .dependencies_provider import (
    VisualizationDependenciesProvider
)
from .provider_factories import (
    StandardDependenciesProviderFactory,
    CachedDependenciesProviderFactory,
    TestDependenciesProviderFactory
)
from .visualization_service_locator import (
    VisualizationServiceLocator,
    get_visualization_service_locator,
    create_real_data_provider,
    create_mock_data_provider
)
from .factory_types import FactoryType

__all__ = [
    'DependenciesProvidable',
    'DependenciesProviderFactoryable',
    'VisualizationDependenciesProvider',
    'StandardDependenciesProviderFactory',
    'CachedDependenciesProviderFactory',
    'TestDependenciesProviderFactory',
    'VisualizationServiceLocator',
    'get_visualization_service_locator',
    'create_real_data_provider',
    'create_mock_data_provider',
    'FactoryType'
]
