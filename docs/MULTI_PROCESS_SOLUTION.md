# Простой и эффективный мультипроцессинг для investRobot

## 🎯 **Предложенное решение**

Я создал простую и эффективную систему для запуска независимых процессов для каждого робота/счёта, которая полностью интегрируется с существующей архитектурой investRobot.

## 🏗️ **Архитектура решения**

### Основные компоненты:

1. **`AccountConfig`** - конфигурация для отдельного счёта
2. **`RobotProcess`** - управление отдельным процессом робота  
3. **`ProcessManager`** - менеджер для управления всеми процессами
4. **`run_multi_account.py`** - главный лонгчер
5. **`multi_robot.sh`** - удобные bash скрипты

### Ключевые преимущества:

✅ **Полная изоляция процессов** - каждый счёт в отдельном OS процессе  
✅ **Независимые ресурсы** - отдельная память, логи, визуализация  
✅ **Простое управление** - запуск/остановка/перезапуск отдельных роботов  
✅ **Автоматическое управление портами** - уникальные порты для каждого счёта  
✅ **Graceful shutdown** - корректное закрытие позиций при остановке  
✅ **Интеграция с существующей системой** - использует весь investRobot как есть  

## 🚀 **Быстрый старт**

### 1. Создание конфигурации
```bash
# Создать пример конфигурации
./tools/multi_robot.sh create-config
```

### 2. Настройка аккаунтов  
Отредактируйте `accounts_config.json`:
```json
{
  "accounts": [
    {
      "account_id": "account_1",
      "token": "your_token",
      "sandbox_token": "sandbox_token", 
      "figi": "FUTIMOEXF000",
      "deposit": 100000.0,
      "visualization_port": 8050
    },
    {
      "account_id": "account_2",
      "token": "your_token",
      "sandbox_token": "sandbox_token",
      "figi": "SBER", 
      "deposit": 50000.0,
      "visualization_port": 8051
    }
  ]
}
```

### 3. Запуск системы
```bash
# Интерактивный режим (рекомендуется)
./tools/multi_robot.sh start

# Daemon режим
./tools/multi_robot.sh daemon
```

## 🎮 **Управление роботами**

В интерактивном режиме доступны команды:

```bash
> status                    # Статус всех роботов
> start                     # Запустить всех роботов  
> stop                      # Остановить всех роботов
> start account_1           # Запустить конкретный робот
> stop account_1            # Остановить конкретный робот  
> restart account_1         # Перезапустить конкретный робот
> quit                      # Выход
```

## 📊 **Мониторинг**

### Визуализация
Каждый робот имеет свой дашборд:
- Счёт 1: http://127.0.0.1:8050
- Счёт 2: http://127.0.0.1:8051  
- И так далее...

### Логи
Отдельные логи для каждого счёта:
```bash
data/logs/robot_account_1.log
data/logs/robot_account_2.log
```

### Bash скрипты
```bash
./tools/multi_robot.sh status    # Статус daemon
./tools/multi_robot.sh logs      # Просмотр логов
./tools/multi_robot.sh stop      # Остановка daemon
```

## ⚙️ **Конфигурация**

### Полные параметры AccountConfig:
```python
@dataclass
class AccountConfig:
    # Обязательные
    account_id: str                    # ID счёта Tinkoff
    token: str                         # API токен
    sandbox_token: str                 # Sandbox токен
    
    # Торговые
    figi: str = "FUTIMOEXF000"         # Инструмент
    deposit: float = 100000.0          # Депозит
    
    # Риск-менеджмент  
    max_daily_loss: float = 5000.0     # Макс. дневные потери
    max_position_size: float = 50000.0 # Макс. размер позиции
    stop_loss_threshold: float = 2.0   # Стоп-лосс %
    
    # Сессия
    auto_close_positions: bool = True   # Автозакрытие позиций
    end_of_day_close: bool = True      # Закрытие в конце дня
    close_time: time = time(23, 50)    # Время закрытия
    
    # Визуализация
    enable_visualization: bool = True   # Включить дашборд
    visualization_port: int = 8050     # Порт дашборда
    
    # Стратегии
    strategy_config: dict = None       # Параметры стратегий
```

## 🔧 **Продвинутое использование**

### Один счёт для тестирования:
```bash
python run_multi_account.py \
  --account-id "test_account" \
  --token "your_token" \
  --figi "FUTIMOEXF000" \
  --interactive
```

### Daemon в продакшене:
```bash
nohup python run_multi_account.py \
  --config accounts_config.json \
  --daemon > multi_robot.log 2>&1 &
```

### Программное управление:
```python
from robotlib.multiprocess import ProcessManager, AccountConfig

# Создаём менеджер
manager = ProcessManager()

# Добавляем счёт
config = AccountConfig(
    account_id="test_account",
    token="your_token", 
    sandbox_token="sandbox_token"
)
manager.add_account(config)

# Запускаем
manager.start_all()

# Статус
manager.print_status()

# Останавливаем
manager.stop_all()
```

## 🛡️ **Безопасность и отказоустойчивость**

### Изоляция процессов:
- Падение одного робота не влияет на другие
- Независимые пространства памяти
- Отдельные подключения к API

### Graceful shutdown:
- Корректное закрытие позиций при остановке
- Обработка сигналов SIGTERM/SIGINT  
- Автоматическая очистка ресурсов

### Восстановление:
- Автоматический перезапуск при ошибках
- Мониторинг состояния процессов
- Логирование всех событий

## 📈 **Масштабирование**

Система легко масштабируется:

- **Вертикально**: больше счётов на одной машине
- **Горизонтально**: распределение по разным серверам  
- **Ресурсы**: автоматическое распределение портов и CPU

## 🎯 **Интеграция с существующей системой**

Решение полностью совместимо с investRobot:

✅ Использует существующий [`TradingSession`](file:///Users/vladimirkokhanevich/Projects/investRobot/robotlib/trading/trading_session.py)  
✅ Применяет [`SessionController`](file:///Users/vladimirkokhanevich/Projects/investRobot/robotlib/trading/session_controller.py)  
✅ Задействует [`DI Container`](file:///Users/vladimirkokhanevich/Projects/investRobot/robotlib/trading/di_container.py)  
✅ Поддерживает все стратегии  
✅ Сохраняет визуализацию и мониторинг  
✅ Следует всем правилам проекта  

**Результат**: мощная система мультипроцессинга, которая превращает investRobot в масштабируемое решение для управления множественными торговыми счетами с полной изоляцией и простым управлением.