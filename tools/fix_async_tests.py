#!/usr/bin/env python3
"""
Скрипт для автоматического исправления async тестов
"""
import os
import re
from pathlib import Path


def fix_async_test_file(file_path: str) -> bool:
    """
    Исправляет async тесты в файле, заменяя unittest.TestCase на pytest
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Добавляем импорт pytest если его нет
    if 'import pytest' not in content:
        content = content.replace(
            'import unittest',
            'import unittest\nimport pytest'
        )
    
    # Заменяем async def test_ на @pytest.mark.asyncio\nasync def test_
    pattern = r'(\s+)(async def test_\w+)'
    replacement = r'\1@pytest.mark.asyncio\n\1\2'
    content = re.sub(pattern, replacement, content)
    
    # Если файл изменился, сохраняем его
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False


def main():
    """Основная функция"""
    tests_dir = Path('tests')
    
    # Находим все файлы с async тестами
    async_test_files = []
    for test_file in tests_dir.glob('test_*.py'):
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'async def test_' in content:
                async_test_files.append(test_file)
    
    print(f"Найдено {len(async_test_files)} файлов с async тестами:")
    for file_path in async_test_files:
        print(f"  - {file_path}")
    
    # Исправляем файлы
    fixed_count = 0
    for file_path in async_test_files:
        if fix_async_test_file(str(file_path)):
            print(f"✅ Исправлен: {file_path}")
            fixed_count += 1
        else:
            print(f"⏭️  Пропущен: {file_path}")
    
    print(f"\n🎯 Исправлено {fixed_count} файлов")


if __name__ == '__main__':
    main()


