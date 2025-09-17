# Зависимости проекта investRobot

## Конфигурации зависимостей

### 1. Полная конфигурация (`requirements.txt`)
Содержит **все необходимые** зависимости включая визуализацию:

- **Tinkoff API** - для работы с брокером
- **База данных** - aiosqlite для SQLite
- **Визуализация** - Dash, Plotly для веб-интерфейса
- **Обработка данных** - pandas, numpy
- **Конфигурация** - environs, python-dotenv
- **Время** - pytz, python-dateutil
- **HTTP** - requests
- **Асинхронность** - nest-asyncio
- **Утилиты** - retrying
- **Тестирование** - pytest, pytest-asyncio

### 2. Базовая конфигурация (`requirements-core.txt`)
**Минимальный набор** зависимостей без визуализации:

- **Tinkoff API** - для работы с брокером
- **База данных** - aiosqlite для SQLite
- **Обработка данных** - pandas, numpy
- **Конфигурация** - environs, python-dotenv
- **Время** - pytz, python-dateutil
- **HTTP** - requests
- **Асинхронность** - nest-asyncio
- **Утилиты** - retrying
- **Тестирование** - pytest, pytest-asyncio

### 3. Опциональные зависимости (`requirements-optional.txt`)
Дополнительные пакеты для расширенной функциональности:

- **GPU ускорение** - torch, numba (для оптимизации)
- **Разработка** - jupyter, ipython
- **Мониторинг** - psutil, memory-profiler

## Установка

### Полная конфигурация (с визуализацией):
```bash
pip install -r requirements.txt
```

### Базовая конфигурация (без визуализации):
```bash
pip install -r requirements-core.txt
```

### С опциональными зависимостями:
```bash
pip install -r requirements.txt -r requirements-optional.txt
```

### Только ядро + опциональные:
```bash
pip install -r requirements-core.txt -r requirements-optional.txt
```

## Очистка зависимостей

Файл `requirements.txt` был очищен от:
- Транзитивных зависимостей (зависимости других пакетов)
- Неиспользуемых пакетов
- Дублирующихся зависимостей

Это делает установку быстрее и уменьшает размер виртуального окружения.
