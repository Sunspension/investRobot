#!/usr/bin/env python3
"""
Скрипт для проверки соблюдения правил проекта investRobot
"""
import os
import re
import subprocess
import sys
from pathlib import Path


def check_hasattr_violations():
    """Проверяет нарушения правила hasattr"""
    print("🔍 Проверка hasattr нарушений...")
    violations = []
    
    # Игнорируем библиотеки и тесты
    ignore_paths = ['env/', 'test_', '__pycache__', '.git/']
    
    for py_file in Path('.').rglob('*.py'):
        if any(ignore_path in str(py_file) for ignore_path in ignore_paths):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    # Ищем hasattr с self, но исключаем комментарии и строки
                    if re.search(r'hasattr\s*\(\s*self\s*,', line) and not line.strip().startswith('#'):
                        violations.append(f"{py_file}:{i} - hasattr с self: {line.strip()}")
        except Exception as e:
            print(f"Ошибка чтения {py_file}: {e}")
    
    if violations:
        print("❌ Найдены нарушения hasattr:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ hasattr нарушения не найдены")
        return True


def check_private_attribute_access():
    """Проверяет прямой доступ к приватным атрибутам"""
    print("🔍 Проверка доступа к приватным атрибутам...")
    violations = []
    
    # Игнорируем библиотеки и тесты
    ignore_paths = ['env/', 'test_', '__pycache__', '.git/']
    
    for py_file in Path('.').rglob('*.py'):
        if any(ignore_path in str(py_file) for ignore_path in ignore_paths):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                in_class = False
                class_name = None
                indent_level = 0
                
                for i, line in enumerate(lines, 1):
                    # Определяем, находимся ли мы внутри класса
                    if re.match(r'^\s*class\s+', line):
                        in_class = True
                        class_name = re.match(r'^\s*class\s+(\w+)', line).group(1)
                        indent_level = len(line) - len(line.lstrip())
                    elif line.strip() and len(line) - len(line.lstrip()) <= indent_level:
                        in_class = False
                    
                    # Ищем доступ к приватным атрибутам извне класса
                    # Исключаем присваивания в конструкторе (self._attr = value)
                    # Исключаем обращения к внешним библиотекам (logging.getLogger, etc.)
                    if not in_class and re.search(r'[^_]\._[a-z][a-zA-Z0-9_]*', line):
                        # Исключаем строки с присваиванием в конструкторе
                        if not re.search(r'self\._[a-z][a-zA-Z0-9_]*\s*=', line):
                            # Исключаем обращения к внешним библиотекам
                            if not re.search(r'(logging\.getLogger|\.getLogger|\.setLevel)', line):
                                violations.append(f"{py_file}:{i} - доступ к приватному атрибуту: {line.strip()}")
        except Exception as e:
            print(f"Ошибка чтения {py_file}: {e}")
    
    if violations:
        print("❌ Найдены нарушения доступа к приватным атрибутам:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ Нарушения доступа к приватным атрибутам не найдены")
        return True


def check_imports_in_functions():
    """Проверяет импорты внутри функций"""
    print("🔍 Проверка импортов внутри функций...")
    violations = []
    
    # Игнорируем библиотеки и тесты
    ignore_paths = ['env/', 'test_', '__pycache__', '.git/']
    
    for py_file in Path('.').rglob('*.py'):
        if any(ignore_path in str(py_file) for ignore_path in ignore_paths):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                in_function = False
                indent_level = 0
                
                for i, line in enumerate(lines, 1):
                    # Определяем, находимся ли мы внутри функции
                    if re.match(r'^\s*def\s+', line):
                        in_function = True
                        indent_level = len(line) - len(line.lstrip())
                    elif re.match(r'^\s*class\s+', line):
                        in_function = False
                    elif line.strip() and len(line) - len(line.lstrip()) <= indent_level:
                        in_function = False
                    
                    # Ищем импорты внутри функций
                    if in_function and re.match(r'^\s*import\s+|^\s*from\s+', line):
                        violations.append(f"{py_file}:{i} - импорт внутри функции: {line.strip()}")
        except Exception as e:
            print(f"Ошибка чтения {py_file}: {e}")
    
    if violations:
        print("❌ Найдены импорты внутри функций:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ Импорты внутри функций не найдены")
        return True


def check_database_usage_in_tests():
    """Проверяет использование базы данных в тестах"""
    print("🔍 Проверка использования базы данных в тестах...")
    violations = []

    # Игнорируем библиотеки и виртуальное окружение
    ignore_paths = ['env/', '__pycache__', '.git/']

    # Проверяем только тестовые файлы проекта
    db_patterns = [
        r'\.db\b',  # .db файлы
        r'database',  # database
        r'sqlite',   # sqlite
        r'db_path',  # db_path
        r'market\.db',  # market.db
        r'candles\.db',  # candles.db
        r'init_db',  # init_db
        r'iter_candles',  # iter_candles
    ]

    for py_file in Path('.').rglob('*.py'):
        # Проверяем только тестовые файлы проекта
        if not (py_file.name.startswith('test_') or py_file.name.endswith('_test.py')):
            continue

        # Игнорируем библиотеки
        if any(ignore_path in str(py_file) for ignore_path in ignore_paths):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

                for i, line in enumerate(lines, 1):
                    # Ищем паттерны базы данных, исключая комментарии
                    if not line.strip().startswith('#'):
                        for pattern in db_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                violations.append(f"{py_file}:{i} - использование БД в тесте: {line.strip()}")
                                break
        except Exception as e:
            print(f"Ошибка чтения {py_file}: {e}")

    if violations:
        print("❌ Найдено использование базы данных в тестах:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ Использование базы данных в тестах не найдено")
        return True


def check_mock_dependencies_in_tests():
    """Проверяет использование моков для зависимостей в тестах"""
    print("🔍 Проверка использования моков для зависимостей в тестах...")
    violations = []

    # Игнорируем библиотеки и виртуальное окружение
    ignore_paths = ['env/', '__pycache__', '.git/']

    # Паттерны реальных зависимостей, которые должны быть замоканы
    # Исключаем создание тестируемых объектов (они могут быть реальными)
    real_dependency_patterns = [
        r'requests\.',          # Прямые HTTP запросы
        r'urllib\.',            # Прямые HTTP запросы
        r'socket\.',            # Прямые сокеты
        r'subprocess\.',        # Прямые процессы
        r'open\(',              # Прямое открытие файлов
        r'with open\(',         # Прямое открытие файлов
    ]

    # Паттерны создания объектов, которые должны быть замоканы (НЕ в setUp)
    # Исключаем создание SUT (тестируемых объектов)
    object_creation_patterns = [
        r'TinkoffAPIClient\(',  # Реальные API клиенты
        r'MarketDataStream\(',  # Реальные стримы
        r'PortfolioManager\(',  # Реальные менеджеры
        r'StrategyManager\(',   # Реальные менеджеры
        r'RiskManager\(',       # Реальные менеджеры
        r'OrderExecutor\(',     # Реальные исполнители
    ]
    
    # Паттерны SUT (тестируемых объектов) - они могут быть реальными
    sut_patterns = [
        r'SessionController\(',  # SUT
        r'TradingSession\(',     # SUT
        r'SignalManager\(',      # SUT
    ]

    for py_file in Path('.').rglob('*.py'):
        # Проверяем только тестовые файлы проекта
        if not (py_file.name.startswith('test_') or py_file.name.endswith('_test.py')):
            continue

        # Игнорируем библиотеки
        if any(ignore_path in str(py_file) for ignore_path in ignore_paths):
            continue

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

                in_setup = False
                for i, line in enumerate(lines, 1):
                    # Отслеживаем, находимся ли мы в методе setUp
                    if 'def setUp(' in line:
                        in_setup = True
                    elif line.strip().startswith('def ') and not line.strip().startswith('def setUp('):
                        in_setup = False
                    
                    # Ищем прямые вызовы внешних API (всегда запрещены)
                    if (not line.strip().startswith('#') and 
                        not line.strip().startswith('import') and 
                        not line.strip().startswith('from')):
                        for pattern in real_dependency_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                violations.append(f"{py_file}:{i} - прямое использование внешнего API: {line.strip()}")
                                break
                    
                    # Ищем создание объектов (запрещено только НЕ в setUp)
                    if (not line.strip().startswith('#') and 
                        not line.strip().startswith('import') and 
                        not line.strip().startswith('from') and
                        not in_setup):  # Исключаем setUp методы
                        
                        # Проверяем, не является ли это SUT
                        is_sut = False
                        for sut_pattern in sut_patterns:
                            if re.search(sut_pattern, line, re.IGNORECASE):
                                is_sut = True
                                break
                        
                        # Если это не SUT, проверяем на запрещенные объекты
                        if not is_sut:
                            for pattern in object_creation_patterns:
                                if re.search(pattern, line, re.IGNORECASE):
                                    violations.append(f"{py_file}:{i} - создание реального объекта в тесте: {line.strip()}")
                                    break
        except Exception as e:
            print(f"Ошибка чтения {py_file}: {e}")

    if violations:
        print("❌ Найдено использование реальных зависимостей в тестах:")
        for violation in violations:
            print(f"  {violation}")
        return False
    else:
        print("✅ Все зависимости в тестах замоканы")
        return True


def run_tests():
    """Запускает тесты"""
    print("🧪 Запуск тестов...")
    try:
        result = subprocess.run(['python', '-m', 'pytest', 'tests/', 'test_historical.py', '-v'], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print("✅ Все тесты прошли")
            return True
        else:
            print("❌ Тесты не прошли:")
            print(result.stdout)
            print(result.stderr)
            print("❌ Согласно правилу: анализировать причину падения и исправлять!")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Тесты превысили время ожидания")
        return False
    except Exception as e:
        print(f"❌ Ошибка запуска тестов: {e}")
        return False


def run_linter():
    """Запускает линтер"""
    print("🔍 Запуск линтера...")
    try:
        # Проверяем только наш код, игнорируя библиотеки
        # Игнорируем стилевые ошибки и оставляем только критические
        result = subprocess.run(['python', '-m', 'flake8', 'robotlib/', 'visualization/', 'tests/', 
                               '--ignore=W293,W291,E501,E128,E129,E302,E304,F401,F841,F811,E402,E303,E301,E251,E117,E126,E226,F541,W504,E123,E131,E122,E305,W391'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Линтер не нашел ошибок")
            return True
        else:
            print("❌ Линтер нашел ошибки:")
            print(result.stdout)
            return False
    except Exception as e:
        print(f"❌ Ошибка запуска линтера: {e}")
        return False


def main():
    """Основная функция проверки"""
    print("🚀 Проверка правил проекта investRobot")
    print("=" * 50)
    
    checks = [
        check_hasattr_violations,
        check_private_attribute_access,
        check_imports_in_functions,
        check_database_usage_in_tests,
        check_mock_dependencies_in_tests,
        run_tests,
        run_linter
    ]
    
    passed = 0
    total = len(checks)
    
    for check in checks:
        if check():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Результат: {passed}/{total} проверок прошли")
    
    if passed == total:
        print("🎉 Все правила соблюдены!")
        return 0
    else:
        print("⚠️  Найдены нарушения правил!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
