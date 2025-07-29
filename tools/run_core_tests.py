#!/usr/bin/env python3
"""
Скрипт для запуска основных тестов проекта investRobot
Запускает только тесты критических компонентов
"""
import unittest
import sys
import os

# Добавляем корневую директорию проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def run_core_tests():
    """Запуск основных тестов"""
    print("🧪 Запуск основных тестов проекта investRobot...")
    print("=" * 50)
    
    # Список основных тестовых модулей
    core_test_modules = [
        'tests.test_money',
        'tests.test_signal_manager', 
        'tests.test_tinkoff_api_client',
        'tests.test_portfolio_manager',
        'tests.test_order_executor',
        'tests.test_trading_session'
    ]
    
    # Загружаем тесты
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    for module_name in core_test_modules:
        try:
            module = __import__(module_name, fromlist=[''])
            tests = loader.loadTestsFromModule(module)
            suite.addTests(tests)
            print(f"✅ Загружен модуль: {module_name}")
        except ImportError as e:
            print(f"❌ Ошибка загрузки модуля {module_name}: {e}")
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Выводим результаты
    print("\n" + "=" * 50)
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    success = total_tests - failures - errors
    
    print(f"📊 Результаты тестирования:")
    print(f"   Всего тестов: {total_tests}")
    print(f"   Успешно: {success} ✅")
    print(f"   Провалы: {failures} ❌")
    print(f"   Ошибки: {errors} ⚠️")
    print(f"   Покрытие: {(success/total_tests)*100:.1f}%")
    
    if failures == 0 and errors == 0:
        print("\n🎉 Все основные тесты прошли успешно!")
        return True
    else:
        print(f"\n⚠️  {failures + errors} тестов не прошли")
        return False

if __name__ == '__main__':
    success = run_core_tests()
    sys.exit(0 if success else 1)
