# Автоматическое закрытие позиций в конце дня

## Реализованная функциональность

Система поддерживает автоматическое закрытие позиций в конце торгового дня с настраиваемыми параметрами и предупреждениями.

## Новые параметры конфигурации

### **TradingConfig обновлен:**

```python
class TradingConfig:
    def __init__(
        self, 
        figi: str, 
        auto_close_positions: bool = True,
        end_of_day_close: bool = True,           # ← НОВОЕ: Включить закрытие в конце дня
        close_time: time = time(23, 50),         # ← НОВОЕ: Время закрытия позиций
        warning_periods: list[int] = [600, 300, 60]  # ← НОВОЕ: Периоды предупреждений
    ):
```

### **Параметры:**

- **`end_of_day_close`**: Включить/выключить закрытие в конце дня
- **`close_time`**: Время закрытия позиций (по умолчанию 23:50)
- **`warning_periods`**: Периоды предупреждений в секундах (по умолчанию 10, 5, 1 минута)

## Примеры использования

### **1. Стандартная конфигурация:**
```python
config = TradingConfig(
    figi="FUTIMOEXF000",
    end_of_day_close=True,        # Включить закрытие в конце дня
    close_time=time(23, 50),      # Закрывать в 23:50
    warning_periods=[600, 300, 60] # Предупреждения за 10, 5, 1 минуту
)
```

### **2. Пользовательское время закрытия:**
```python
config = TradingConfig(
    figi="FUTIMOEXF000",
    close_time=time(18, 0),       # Закрывать в 18:00
    warning_periods=[300, 60]     # Предупреждения за 5 и 1 минуту
)
```

### **3. Отключить закрытие в конце дня:**
```python
config = TradingConfig(
    figi="FUTIMOEXF000",
    end_of_day_close=False        # Отключить автоматическое закрытие
)
```

### **4. Только предупреждения без закрытия:**
```python
config = TradingConfig(
    figi="FUTIMOEXF000",
    end_of_day_close=False,       # Не закрывать автоматически
    warning_periods=[600, 300]    # Но показывать предупреждения
)
```

## Логика работы

### **1. Проверка времени в торговом цикле:**
```python
async def run_trading_loop(self) -> None:
    while self._is_running:
        # Проверяем, нужно ли закрыть позиции в конце дня
        if self.config.end_of_day_close:
            time_to_close = await self._get_time_to_close()
            
            if time_to_close <= 0:
                # Время закрыть позиции
                self.logger.info("Конец торгового дня, закрываем позиции")
                await self._close_all_positions()
                await self.stop()
                break
            else:
                # Проверяем предупреждения
                await self._check_close_warnings(time_to_close, shown_warnings)
        
        # Обычная торговля...
```

### **2. Вычисление времени до закрытия:**
```python
async def _get_time_to_close(self) -> int:
    """Получает время до закрытия позиций в секундах"""
    # Получаем текущее время в Москве
    now = datetime.now(moscow_tz)
    
    # Создаем время закрытия на сегодня
    close_datetime = moscow_tz.localize(
        datetime.combine(now.date(), self.config.close_time)
    )
    
    # Если время закрытия уже прошло сегодня, берем завтра
    if now >= close_datetime:
        close_datetime = moscow_tz.localize(
            datetime.combine(now.date() + timedelta(days=1), self.config.close_time)
        )
    
    # Вычисляем разность в секундах
    return int((close_datetime - now).total_seconds())
```

### **3. Система предупреждений:**
```python
async def _check_close_warnings(self, time_to_close: int, shown_warnings: set) -> None:
    """Проверяет и показывает предупреждения о скором закрытии"""
    for warning_period in self.config.warning_periods:
        if time_to_close <= warning_period and warning_period not in shown_warnings:
            # Показываем предупреждение
            minutes = warning_period // 60
            seconds = warning_period % 60
            
            if minutes > 0:
                message = f"До закрытия позиций осталось {minutes} минут"
                if seconds > 0:
                    message += f" {seconds} секунд"
            else:
                message = f"До закрытия позиций осталось {seconds} секунд"
            
            self.logger.warning(message)
            shown_warnings.add(warning_period)
            break  # Показываем только одно предупреждение за раз
```

## Примеры логов

### **Нормальная работа с предупреждениями:**
```
[INFO] Запуск торгового цикла...
[INFO] Продолжаем торговлю...
[WARNING] До закрытия позиций осталось 10 минут
[INFO] Продолжаем торговлю...
[WARNING] До закрытия позиций осталось 5 минут
[INFO] Продолжаем торговлю...
[WARNING] До закрытия позиций осталось 1 минута
[INFO] Продолжаем торговлю...
[INFO] Конец торгового дня, закрываем позиции
[INFO] Закрытие всех позиций через стратегии...
[INFO] Позиция закрыта в стратегии LongStrategy: OrderResult(...)
[INFO] Торговая сессия остановлена
```

### **Отключенное закрытие:**
```
[INFO] Запуск торгового цикла...
[INFO] Продолжаем торговлю...
[INFO] Продолжаем торговлю...
[INFO] Продолжаем торговлю...
# Торговля продолжается без закрытия позиций
```

## **Использование**

Система автоматически проверяет время в торговом цикле и закрывает позиции при достижении настроенного времени. Предупреждения показываются заранее согласно настроенным периодам.
