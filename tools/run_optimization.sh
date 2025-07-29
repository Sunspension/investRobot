#!/bin/bash
# Скрипт для запуска оптимизации с правильными путями

# Переходим в корневую папку проекта
cd "$(dirname "$0")/.."

# Активируем виртуальное окружение
source env/bin/activate

# Создаем папки для логов и результатов
mkdir -p data/logs
mkdir -p data/optimization_results

# Запускаем оптимизацию
echo "🚀 Запуск оптимизации..."
echo "📁 Логи будут сохранены в: data/logs/"
echo "📊 Результаты будут сохранены в: data/optimization_results/"
echo "=" * 60

# Запускаем с временной меткой
TS=$(date +%Y%m%d_%H%M%S)
nohup python -u optimization/optimizer.py --all > data/logs/optimization_${TS}.log 2>&1 &

echo "✅ Оптимизация запущена в фоне"
echo "📋 PID: $!"
echo "📁 Лог файл: data/logs/optimization_${TS}.log"
echo "🔍 Для мониторинга: tail -f data/logs/optimization_${TS}.log"
