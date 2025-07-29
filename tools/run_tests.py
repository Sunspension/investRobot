#!/usr/bin/env python3
"""
Скрипт для запуска всех тестов проекта
"""
import sys
import subprocess
import os

def run_tests():
    """Запускает все тесты проекта"""
    print("🧪 Запуск тестов проекта investRobot...")
    print("=" * 50)
    
    try:
        # Запускаем тесты
        # Переходим в корневую папку проекта
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        result = subprocess.run([
            sys.executable, "-m", "unittest", "discover", "tests", "-v"
        ], capture_output=True, text=True, cwd=project_root)
        
        # Выводим результат
        print(result.stdout)
        if result.stderr:
            print("Ошибки:")
            print(result.stderr)
        
        # Анализируем результат
        if result.returncode == 0:
            print("=" * 50)
            print("✅ Все тесты прошли успешно!")
            
            # Подсчитываем количество тестов
            lines = result.stdout.split('\n')
            for line in lines:
                if "Ran" in line and "tests" in line:
                    print(f"📊 {line}")
                    break
        else:
            print("=" * 50)
            print("❌ Некоторые тесты не прошли!")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при запуске тестов: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
