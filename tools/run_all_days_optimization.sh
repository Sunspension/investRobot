#!/bin/bash
# Скрипт для запуска оптимизации всех дней

# Переходим в корневую папку проекта
cd "$(dirname "$0")/.."

# Активируем виртуальное окружение
source env/bin/activate

# Создаем папки для логов и результатов
mkdir -p data/logs
mkdir -p data/optimization_results

# Запускаем оптимизацию всех дней
echo "🚀 Запуск оптимизации всех дней..."
echo "📁 Логи будут сохранены в: data/logs/"
echo "📊 Результаты будут сохранены в: data/optimization_results/"
echo "=" * 60

# Запускаем с временной меткой
TS=$(date +%Y%m%d_%H%M%S)
nohup python -u optimization/optimizer.py --all > data/logs/all_days_optimization_${TS}.log 2>&1 &

echo "✅ Оптимизация всех дней запущена в фоне"
echo "📋 PID: $!"
echo "📁 Лог файл: data/logs/all_days_optimization_${TS}.log"
echo "🔍 Для мониторинга: tail -f data/logs/all_days_optimization_${TS}.log"
echo ""
echo "⏱️  Примерное время выполнения:"
echo "   - 1 день: ~12 минут"
echo "   - 21 день (декабрь 2024): ~4.2 часа"
