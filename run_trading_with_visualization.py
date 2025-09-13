#!/usr/bin/env python3
"""
Скрипт для запуска торговли с визуализацией
"""
import asyncio
import sys
import logging
import warnings
import argparse
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Парсим аргументы командной строки
parser = argparse.ArgumentParser(description='Запуск торговли с визуализацией')
parser.add_argument('--debug', '-d', action='store_true', help='Включить детальные логи')
parser.add_argument('--verbose', '-v', action='store_true', help='Включить все логи')
args = parser.parse_args()

# Настраиваем логирование
if args.verbose:
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
elif args.debug:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
else:
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# Отключаем избыточные логи Flask/Dash
from visualization.logging_config import disable_verbose_logging
disable_verbose_logging(enable_debug_logs=args.debug or args.verbose)

from examples.trading_with_visualization import main

if __name__ == "__main__":
    print("🚀 Запуск торговли с визуализацией...")
    print("📊 Визуализатор будет доступен по адресу: http://127.0.0.1:8050")
    print("⏹️ Для остановки нажмите Ctrl+C")
    if args.debug:
        print("🔍 Режим отладки включен - детальные логи")
    if args.verbose:
        print("📝 Подробные логи включены - все сообщения")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Остановка по запросу пользователя")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

