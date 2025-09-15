#!/usr/bin/env python3
import pytest
import inspect

# Глобально подключаем поддержку async-тестов для корневых тестовых файлов
pytest_plugins = ('pytest_asyncio',)

def pytest_configure(config):
    config.addinivalue_line('markers', 'asyncio: mark test as async')

def pytest_collection_modifyitems(config, items):
    # Автоматически помечаем async-функции маркером asyncio
    for item in items:
        try:
            obj = getattr(item, 'obj', None)
            if obj and inspect.iscoroutinefunction(obj):
                item.add_marker(pytest.mark.asyncio)
        except Exception:
            pass

