#!/bin/bash
# Скрипт управления мультироботами

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/accounts_config.json"
PYTHON_CMD="python3"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Отключить цвет

# Функции
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    log_info "Проверка требований..."
    
    # Проверка Python
    if ! command -v $PYTHON_CMD &> /dev/null; then
        log_error "Python3 не найден. Пожалуйста, установите Python 3.10+"
        exit 1
    fi
    
    # Проверка версии Python
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    log_info "Версия Python: $PYTHON_VERSION"
    
    # Проверка существования виртуального окружения
    if [ ! -d "$PROJECT_ROOT/env" ]; then
        log_warning "Виртуальное окружение не найдено"
        read -p "Создать виртуальное окружение? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_venv
        fi
    fi
    
    # Проверка файла конфигурации
    if [ ! -f "$CONFIG_FILE" ]; then
        log_warning "Файл конфигурации не найден: $CONFIG_FILE"
        read -p "Создать пример конфигурации? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_config
        fi
    fi
}

create_venv() {
    log_info "Создание виртуального окружения..."
    $PYTHON_CMD -m venv "$PROJECT_ROOT/env"
    
    log_info "Активация виртуального окружения..."
    source "$PROJECT_ROOT/env/bin/activate"
    
    log_info "Установка зависимостей..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
    
    log_success "Виртуальное окружение создано и настроено"
}

create_config() {
    log_info "Создание примера конфигурации..."
    $PYTHON_CMD "$PROJECT_ROOT/run_multi_account.py" --create-config
    log_success "Пример конфигурации создан: $CONFIG_FILE"
    log_warning "Пожалуйста, отредактируйте $CONFIG_FILE с вашими реальными учётными данными"
}

activate_env() {
    if [ -d "$PROJECT_ROOT/env" ]; then
        source "$PROJECT_ROOT/env/bin/activate"
        log_info "Виртуальное окружение активировано"
    else
        log_warning "Виртуальное окружение не найдено, используем системный Python"
    fi
}

start_interactive() {
    log_info "Запуск многоаккаунтных роботов в интерактивном режиме..."
    activate_env
    $PYTHON_CMD "$PROJECT_ROOT/run_multi_account.py" --config "$CONFIG_FILE" --interactive
}

start_daemon() {
    log_info "Запуск многоаккаунтных роботов в режиме daemon..."
    activate_env
    
    # Создаём папку для логов
    mkdir -p "$PROJECT_ROOT/data/logs"
    
    # Запуск в фоновом режиме
    nohup $PYTHON_CMD "$PROJECT_ROOT/run_multi_account.py" --config "$CONFIG_FILE" --daemon > "$PROJECT_ROOT/data/logs/multi_robot_daemon.log" 2>&1 &
    
    local PID=$!
    echo $PID > "$PROJECT_ROOT/data/multi_robot.pid"
    
    log_success "Multi-robot daemon запущен с PID: $PID"
    log_info "Логи: $PROJECT_ROOT/data/logs/multi_robot_daemon.log"
    log_info "Для остановки: $SCRIPT_DIR/multi_robot.sh stop"
}

stop_daemon() {
    if [ -f "$PROJECT_ROOT/data/multi_robot.pid" ]; then
        local PID=$(cat "$PROJECT_ROOT/data/multi_robot.pid")
        log_info "Остановка daemon с PID: $PID"
        
        if kill -0 $PID 2>/dev/null; then
            kill -TERM $PID
            
            # Ожидаем корректного завершения
            for i in {1..30}; do
                if ! kill -0 $PID 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            
            # Принудительно убиваем, если всё ещё запущено
            if kill -0 $PID 2>/dev/null; then
                log_warning "Корректная остановка не удалась, принудительно завершаем..."
                kill -KILL $PID
            fi
            
            log_success "Daemon остановлен"
        else
            log_warning "Процесс $PID не запущен"
        fi
        
        rm -f "$PROJECT_ROOT/data/multi_robot.pid"
    else
        log_warning "PID file not found, daemon may not be running"
    fi
}

status_daemon() {
    if [ -f "$PROJECT_ROOT/data/multi_robot.pid" ]; then
        local PID=$(cat "$PROJECT_ROOT/data/multi_robot.pid")
        
        if kill -0 $PID 2>/dev/null; then
            log_success "Daemon запущен с PID: $PID"
            
            # Показываем последние логи
            if [ -f "$PROJECT_ROOT/data/logs/multi_robot_daemon.log" ]; then
                log_info "Последние логи:"
                tail -10 "$PROJECT_ROOT/data/logs/multi_robot_daemon.log"
            fi
        else
            log_warning "Daemon PID file exists but process is not running"
            rm -f "$PROJECT_ROOT/data/multi_robot.pid"
        fi
    else
        log_info "Daemon is not running"
    fi
}

test_single() {
    log_info "Testing single account mode..."
    
    read -p "Enter account ID: " ACCOUNT_ID
    read -p "Enter token: " TOKEN
    read -p "Enter sandbox token (optional): " SANDBOX_TOKEN
    read -p "Enter FIGI (default: FUTIMOEXF000): " FIGI
    
    FIGI=${FIGI:-FUTIMOEXF000}
    
    activate_env
    $PYTHON_CMD "$PROJECT_ROOT/run_multi_account.py" \
        --account-id "$ACCOUNT_ID" \
        --token "$TOKEN" \
        --sandbox-token "$SANDBOX_TOKEN" \
        --figi "$FIGI" \
        --interactive
}

show_help() {
    echo "Multi-Robot Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup          - Check requirements and setup environment"
    echo "  create-config  - Create sample configuration file"
    echo "  start          - Start robots in interactive mode"
    echo "  daemon         - Start robots in daemon mode"
    echo "  stop           - Stop daemon"
    echo "  status         - Show daemon status"
    echo "  test           - Test single account mode"
    echo "  logs           - Show daemon logs"
    echo "  help           - Show this help"
    echo ""
    echo "Configuration file: $CONFIG_FILE"
}

show_logs() {
    if [ -f "$PROJECT_ROOT/data/logs/multi_robot_daemon.log" ]; then
        log_info "Showing daemon logs (press Ctrl+C to exit):"
        tail -f "$PROJECT_ROOT/data/logs/multi_robot_daemon.log"
    else
        log_warning "Daemon log file not found"
    fi
}

# Основная логика скрипта
case "${1:-help}" in
    "setup")
        check_requirements
        ;;
    "create-config")
        create_config
        ;;
    "start")
        check_requirements
        start_interactive
        ;;
    "daemon")
        check_requirements
        start_daemon
        ;;
    "stop")
        stop_daemon
        ;;
    "status")
        status_daemon
        ;;
    "test")
        check_requirements
        test_single
        ;;
    "logs")
        show_logs
        ;;
    "help"|*)
        show_help
        ;;
esac