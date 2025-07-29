#!/bin/bash
# Скрипт для мониторинга оптимизации всех дней

# Переходим в корневую папку проекта
cd "$(dirname "$0")/.."

LOG_FILE="data/logs/all_days_optimization_20250910_125423.log"

echo "🔍 МОНИТОРИНГ ОПТИМИЗАЦИИ ВСЕХ ДНЕЙ"
echo "=================================="
echo "📁 Лог файл: $LOG_FILE"
echo ""

# Проверяем, что файл существует
if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Лог файл не найден: $LOG_FILE"
    exit 1
fi

# Функция для показа прогресса
show_progress() {
    echo "📊 ПРОГРЕСС:"
    echo "==========="
    
    # Показываем текущий день
    CURRENT_DAY=$(tail -100 "$LOG_FILE" | grep "ДЕНЬ [0-9]" | tail -1)
    if [ ! -z "$CURRENT_DAY" ]; then
        echo "🎯 $CURRENT_DAY"
    fi
    
    # Показываем завершенные дни
    COMPLETED_DAYS=$(grep "✅ День.*завершен успешно" "$LOG_FILE" | wc -l)
    echo "✅ Завершено дней: $COMPLETED_DAYS/21"
    
    # Показываем лучшие результаты
    echo ""
    echo "🏆 ЛУЧШИЕ РЕЗУЛЬТАТЫ:"
    echo "==================="
    grep "🏆 Лучший результат:" "$LOG_FILE" | tail -5
    
    # Показываем текущую скорость
    echo ""
    echo "⚡ ТЕКУЩАЯ СКОРОСТЬ:"
    echo "=================="
    tail -10 "$LOG_FILE" | grep "Скорость:" | tail -1
    
    # Показываем время
    echo ""
    echo "⏰ ВРЕМЯ:"
    echo "========"
    echo "Начало: $(head -10 "$LOG_FILE" | grep "Начало:" | tail -1)"
    echo "Текущее: $(date '+%H:%M:%S')"
}

# Показываем прогресс
show_progress

echo ""
echo "🔍 Для непрерывного мониторинга: tail -f $LOG_FILE"
echo "🔄 Для обновления: ./monitor_all_days.sh"
