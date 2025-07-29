#!/bin/bash

# Скрипт для параллельной оптимизации по дням
# Использование: ./parallel_optimize.sh

DB_PATH="../data/market.db"
FIGI="FUTIMOEXF000"
RESULTS_DIR="../data/optimization_results"

# Создаем директорию для результатов
mkdir -p "$RESULTS_DIR"

# Список торговых дней декабря 2024 (без выходных)
TRADING_DAYS=(
    "2024-12-02" "2024-12-03" "2024-12-04" "2024-12-05" "2024-12-06"
    "2024-12-09" "2024-12-10" "2024-12-11" "2024-12-12" "2024-12-13"
    "2024-12-16" "2024-12-17" "2024-12-18" "2024-12-19" "2024-12-20"
    "2024-12-23" "2024-12-24" "2024-12-25" "2024-12-26" "2024-12-27"
    "2024-12-28" "2024-12-30"
)

# Глобальные переменные для отслеживания прогресса
TOTAL_COUNT=0
START_TIME=$(date +%s)
PROGRESS_DIR="/tmp/parallel_optimize_progress"

    # Создаем директорию для отслеживания прогресса
    mkdir -p "$PROGRESS_DIR"
    
    # Сохраняем параметры для фоновых процессов
    echo "$TOTAL_COUNT" > "$PROGRESS_DIR/total_count"
    echo "$START_TIME" > "$PROGRESS_DIR/start_time"

# Функция для обновления прогресса
update_progress() {
    local day=$1
    local status=$2
    
    # Создаем файл для завершенного дня (атомарно)
    echo "$status" > "$PROGRESS_DIR/$day.tmp" && mv "$PROGRESS_DIR/$day.tmp" "$PROGRESS_DIR/$day"
    
    # Подсчитываем завершенные дни (исключаем служебные файлы и считаем уникальные даты)
    local completed_count=$(ls "$PROGRESS_DIR" 2>/dev/null | grep -v -E "(start_time|total_count)" | sort -u | wc -l)
    local start_time=$(cat "$PROGRESS_DIR/start_time" 2>/dev/null || echo "$(date +%s)")
    local total_count=$(cat "$PROGRESS_DIR/total_count" 2>/dev/null || echo "22")
    local elapsed=$(( $(date +%s) - start_time ))
    
    # Проверяем на деление на ноль
    if [ $total_count -gt 0 ]; then
        local progress=$(( (completed_count * 100) / total_count ))
    else
        local progress=0
    fi
    
    local eta=0
    if [ $completed_count -gt 0 ] && [ $completed_count -lt $total_count ]; then
        eta=$(( (elapsed * (total_count - completed_count)) / completed_count ))
    fi
    
    printf "\r📊 Прогресс: [%3d%%] %d/%d завершено | ⏱️  %02d:%02d:%02d | ETA: %02d:%02d:%02d | %s %s" \
        $progress $completed_count $total_count \
        $((elapsed / 3600)) $(( (elapsed % 3600) / 60 )) $((elapsed % 60)) \
        $((eta / 3600)) $(( (eta % 3600) / 60 )) $((eta % 60)) \
        "$status" "$day"
}

# Функция для запуска оптимизации одного дня
optimize_day() {
    local day=$1
    local log_file="$RESULTS_DIR/optimize_${day}.log"
    local result_file="$RESULTS_DIR/result_${day}.json"
    
        # Запускаем полную оптимизацию (137,200 комбинаций на день, ~12 часов)
        ../env/bin/python main_stats.py optimize \
            --db "$DB_PATH" \
            --figi "$FIGI" \
            --from "$day 07:00" \
            --to "$day 18:59" \
            --macd-fast 6:12:1 \
            --macd-slow 10:16:1 \
            --macd-signal 7:10:1 \
            --atr-period 6:10:1 \
            --lookback-min 4:8:1 \
            --lookback-max 18:24:1 \
            --peak-prominence 0.15:0.3:0.05 \
            > "$log_file" 2>&1
    
    # Извлекаем лучший результат из лога
    if grep -q "Best:" "$log_file"; then
        grep "Best:" "$log_file" | tail -1 > "$result_file"
        echo "✅" > "$PROGRESS_DIR/$day"
    else
        echo "❌" > "$PROGRESS_DIR/$day"
    fi
}

# Функция для показа детальных результатов
show_detailed_results() {
    echo ""
    echo "🏆 ДЕТАЛЬНЫЕ РЕЗУЛЬТАТЫ С НАСТРОЙКАМИ:"
    echo "=" * 60
    
    local successful_days=0
    local total_income=0
    local best_day=""
    local best_income=0
    
    for day in "${TRADING_DAYS[@]}"; do
        local log_file="$RESULTS_DIR/optimize_${day}.log"
        if [ -f "$log_file" ] && grep -q "Best:" "$log_file"; then
            local best_line=$(grep "Best:" "$log_file" | tail -1)
            local income=$(echo "$best_line" | grep -o "'income': [0-9]*" | grep -o "[0-9]*")
            local params=$(echo "$best_line" | grep -o "'params': {[^}]*}")
            
            if [ -n "$income" ]; then
                successful_days=$((successful_days + 1))
                total_income=$((total_income + income))
                
                echo "📅 $day (Доход: $income руб):"
                
                # Извлекаем параметры
                local macd_fast=$(echo "$params" | grep -o "'macd_fast': [0-9]*" | grep -o "[0-9]*")
                local macd_slow=$(echo "$params" | grep -o "'macd_slow': [0-9]*" | grep -o "[0-9]*")
                local macd_signal=$(echo "$params" | grep -o "'macd_signal': [0-9]*" | grep -o "[0-9]*")
                local atr_period=$(echo "$params" | grep -o "'atr_period': [0-9]*" | grep -o "[0-9]*")
                local lookback_min=$(echo "$params" | grep -o "'lookback_min': [0-9]*" | grep -o "[0-9]*")
                local lookback_max=$(echo "$params" | grep -o "'lookback_max': [0-9]*" | grep -o "[0-9]*")
                local peak_prominence=$(echo "$params" | grep -o "'peak_prominence': [0-9.]*" | grep -o "[0-9.]*")
                
                echo "   MACD Fast: $macd_fast, MACD Slow: $macd_slow, MACD Signal: $macd_signal"
                echo "   ATR Period: $atr_period, Lookback Min: $lookback_min, Lookback Max: $lookback_max"
                echo "   Peak Prominence: $peak_prominence"
                echo ""
                
                # Отслеживаем лучший день
                if [ "$income" -gt "$best_income" ]; then
                    best_income=$income
                    best_day="$day"
                fi
            fi
        else
            echo "❌ $day: Нет результатов или ошибка"
        fi
    done
    
    echo "📊 ИТОГОВАЯ СТАТИСТИКА:"
    echo "   ✅ Успешно обработано: $successful_days дней"
    echo "   💰 Общий доход: $total_income руб"
    if [ $successful_days -gt 0 ]; then
        echo "   📈 Средний доход: $((total_income / successful_days)) руб"
    fi
    
    if [ -n "$best_day" ]; then
        echo "   🏆 Лучший день: $best_day с доходом $best_income руб"
    fi
}

# Основная функция
main() {
    echo "📊 Параллельная оптимизация параметров"
    echo "📅 Период: декабрь 2024"
    echo "📁 Результаты: $RESULTS_DIR/"
    echo "⏰ Начало: $(date)"
    echo "----------------------------------------"
    
    TOTAL_COUNT=${#TRADING_DAYS[@]}
    echo "📈 Найдено $TOTAL_COUNT торговых дней"
    echo "🔄 Запускаем параллельные процессы..."
    echo ""
    
    # Запускаем оптимизацию для каждого дня параллельно
    pids=()
    all_pids=()
    for day in "${TRADING_DAYS[@]}"; do
        optimize_day "$day" &
        pids+=($!)
        all_pids+=($!)
        echo "📅 Запущен процесс для $day (PID: $!)"
    done
    
    echo ""
    echo "⏳ Ожидаем завершения всех процессов..."
    echo "📊 Запущено ${#pids[@]} процессов"
    echo ""
    
    # Показываем прогресс в реальном времени
    echo "📊 Прогресс: [  0%] 0/$TOTAL_COUNT завершено | ⏱️  00:00:00 | ETA: --:--:-- | 🚀 Запуск..."
    
    # Мониторим прогресс в реальном времени
    while [ ${#pids[@]} -gt 0 ]; do
        sleep 1
        
        # Проверяем завершенные процессы
        new_pids=()
        for pid in "${pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                new_pids+=($pid)
            fi
        done
        pids=("${new_pids[@]}")
        
        # Обновляем прогресс (считаем только файлы с датами, исключая служебные)
        local completed_count=$(ls "$PROGRESS_DIR" 2>/dev/null | grep -v -E "(start_time|total_count)" | wc -l)
        local elapsed=$(( $(date +%s) - START_TIME ))
        local progress=$(( (completed_count * 100) / TOTAL_COUNT ))
        local eta=0
        
        if [ $completed_count -gt 0 ] && [ $completed_count -lt $TOTAL_COUNT ]; then
            eta=$(( (elapsed * (TOTAL_COUNT - completed_count)) / completed_count ))
        fi
        
        printf "\r📊 Прогресс: [%3d%%] %d/%d завершено | ⏱️  %02d:%02d:%02d | ETA: %02d:%02d:%02d | 🔄 Выполняется..." \
            $progress $completed_count $TOTAL_COUNT \
            $((elapsed / 3600)) $(( (elapsed % 3600) / 60 )) $((elapsed % 60)) \
            $((eta / 3600)) $(( (eta % 3600) / 60 )) $((eta % 60))
    done
    
    # Дополнительно ждем завершения всех процессов
    echo ""
    echo "⏳ Дожидаемся полного завершения всех процессов..."
    for pid in "${all_pids[@]}"; do
        wait $pid 2>/dev/null
    done
    
    # Финальная строка прогресса
    echo ""
    echo ""
    echo "🎉 Все процессы завершены!"
    echo "⏰ Конец: $(date)"
    echo ""
    
    # Собираем сводку результатов
    echo "📋 СВОДКА РЕЗУЛЬТАТОВ:"
    echo "----------------------------------------"
    
    best_overall_income=-999999999
    best_overall_day=""
    successful_days=0
    failed_days=0
    total_income=0
    
    for day in "${TRADING_DAYS[@]}"; do
        result_file="$RESULTS_DIR/result_${day}.json"
        if [[ -f "$result_file" ]]; then
            # Извлекаем доход из результата
            income=$(grep -o "'income': [0-9-]*" "$result_file" | grep -o "[0-9-]*")
            if [[ -n "$income" ]]; then
                echo "📅 $day: доход = $income руб"
                successful_days=$((successful_days + 1))
                total_income=$((total_income + income))
                if [[ $income -gt $best_overall_income ]]; then
                    best_overall_income=$income
                    best_overall_day=$day
                fi
            else
                echo "❌ $day: не удалось извлечь доход"
                failed_days=$((failed_days + 1))
            fi
        else
            echo "❌ $day: ошибка обработки"
            failed_days=$((failed_days + 1))
        fi
    done
    
    # Показываем детальные результаты с настройками
    show_detailed_results
    
    echo ""
    echo "📁 Все результаты сохранены в директории: $RESULTS_DIR/"
    echo "📊 Логи процессов: $RESULTS_DIR/optimize_*.log"
    echo "🎯 Лучшие результаты: $RESULTS_DIR/result_*.json"
    
    # Очищаем временные файлы прогресса
    rm -rf "$PROGRESS_DIR"
    echo ""
    echo "🧹 Временные файлы очищены"
}

# Обработчик сигналов для очистки при прерывании
cleanup() {
    echo ""
    echo "🛑 Получен сигнал прерывания. Очищаем временные файлы..."
    rm -rf "$PROGRESS_DIR"
    exit 1
}

# Устанавливаем обработчики сигналов
trap cleanup SIGINT SIGTERM

# Запускаем основную функцию
main "$@"