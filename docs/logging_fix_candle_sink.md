# Исправление логирования в run_candle_sink.py

## 🚨 **Проблема:**
```
Не удалось загрузить исторические данные. Ответ: GetCandlesResponse(candles=[])
Не удалось загрузить исторические данные. Ответ: GetCandlesResponse(candles=[])
Watchdog уже запущен
```

**Логи от `candle_sink` не показывали время, что затрудняло анализ проблем.**

## ✅ **Решение:**

### **Добавлена настройка логирования в `run_candle_sink.py`:**
```python
from robotlib.utils.logger import get_logger, setup_logging
import logging

# Настраиваем логирование с датой
setup_logging(level=logging.INFO, log_file='data/logs/candle_sink.log')
logger = get_logger(__name__)
```

### **Добавлена настройка логирования в `run_market_ingestor.py`:**
```python
from robotlib.utils.logger import get_logger, setup_logging
import logging

# Настраиваем логирование с датой
setup_logging(level=logging.INFO, log_file='data/logs/market_ingestor.log')
logger = get_logger(__name__)
```

## 📊 **Результат:**

### **До исправления:**
```
Не удалось загрузить исторические данные. Ответ: GetCandlesResponse(candles=[])
Watchdog уже запущен
```

### **После исправления:**
```
2025-09-26 21:37:25 - investRobot.run_candle_sink - INFO - Запуск стрима рыночных данных для FUTIMOEXF000
2025-09-26 21:37:25 - investRobot.run_candle_sink - WARNING - Не удалось загрузить исторические данные. Ответ: GetCandlesResponse(candles=[])
2025-09-26 21:37:25 - investRobot.run_candle_sink - INFO - Watchdog уже запущен
```

## 🎯 **Преимущества:**

### ✅ **Улучшенная диагностика:**
- **Время событий**: Четко видно, когда произошло событие
- **Файловые логи**: Логи сохраняются в `data/logs/candle_sink.log`
- **Консольные логи**: Логи выводятся в консоль с датой
- **Уровни логирования**: INFO, WARNING, ERROR с соответствующими цветами

### ✅ **Консистентность:**
- **Единый формат**: Одинаковый формат даты во всех логах
- **Централизованная настройка**: Используется `setup_logging` из `robotlib.utils.logger`
- **Файловые логи**: Отдельные файлы для каждого процесса

## 🚀 **Использование:**

### **Консольные логи:**
```bash
2025-09-26 21:37:25 - investRobot.run_candle_sink - INFO - Запуск стрима рыночных данных
2025-09-26 21:37:25 - investRobot.run_candle_sink - WARNING - Предупреждение
2025-09-26 21:37:25 - investRobot.run_candle_sink - ERROR - Ошибка
```

### **Файловые логи:**
```bash
# data/logs/candle_sink.log
2025-09-26 21:37:25 - investRobot.run_candle_sink - INFO - Запуск стрима рыночных данных
2025-09-26 21:37:25 - investRobot.run_candle_sink - WARNING - Предупреждение
2025-09-26 21:37:25 - investRobot.run_candle_sink - ERROR - Ошибка
```

## 📝 **Примечания:**

- **Формат даты**: `YYYY-MM-DD HH:MM:SS` - международный стандарт
- **Часовой пояс**: Логи записываются в локальном времени системы
- **Производительность**: Изменения не влияют на производительность логирования
- **Обратная совместимость**: Существующие логи не сломаются

---

*Исправление применено: 2025-01-27*
