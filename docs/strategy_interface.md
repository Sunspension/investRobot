# Интерфейс стратегий

## Обзор

Система торговых стратегий была рефакторена для поддержки произвольного количества стратегий через единый интерфейс `StrategyInterface`.

## Архитектура

### StrategyInterface

Базовый интерфейс для всех торговых стратегий:

```python
class StrategyInterface(ABC):
    @property
    def income(self) -> float:
        """Возвращает текущий доход стратегии"""
        
    @property
    def position(self) -> int:
        """Возвращает текущую позицию стратегии"""
        
    def execute(self, signal: Signal) -> List[OrderIntent]:
        """Выполняет торговую логику на основе сигнала"""
        
    def close_position(self, candle: Candle | HistoricCandle) -> OrderIntent | None:
        """Закрывает все открытые позиции"""
        
    @property
    def strategy_name(self) -> str:
        """Возвращает название стратегии"""
```

### StrategyManager

Обновленный менеджер стратегий поддерживает:

- **Произвольное количество стратегий** через массив
- **Единый интерфейс** для всех стратегий
- **Гибкую конфигурацию** параметров для каждой стратегии
- **Индивидуальный доступ** к результатам каждой стратегии

## Использование

### Дефолтные стратегии

```python
# Создает LongStrategy + ShortStrategy с дефолтными параметрами
sm = StrategyManager()
```

### Кастомные стратегии

```python
# Только лонг стратегия (risk_manager и portfolio_manager - обязательные параметры)
long_only = StrategyManager(
    signal_manager=signal_manager,
    risk_manager=risk_manager,
    portfolio_manager=portfolio_manager,
    strategies=[LongStrategy(risk_manager=risk_manager, portfolio_manager=portfolio_manager)]
)

# Комбинация стратегий (все используют параметры из RiskManager)
custom_strategies = [
    LongStrategy(risk_manager=risk_manager, portfolio_manager=portfolio_manager),
    ShortStrategy(risk_manager=risk_manager, portfolio_manager=portfolio_manager)
]
custom_sm = StrategyManager(
    signal_manager=signal_manager,
    risk_manager=risk_manager,
    portfolio_manager=portfolio_manager,
    strategies=custom_strategies
)
```

### Доступ к результатам

```python
# Общий доход всех стратегий
total_income = sm.income

# Доход конкретной стратегии (по классу)
long_income = sm.get_strategy_income(LongStrategy)
short_income = sm.get_strategy_income(ShortStrategy)

# Позиция конкретной стратегии (по классу)
long_position = sm.get_strategy_position(LongStrategy)
```

## Создание новых стратегий

Для создания новой стратегии нужно:

1. **Наследоваться от StrategyInterface**
2. **Реализовать все абстрактные методы**
3. **Использовать атрибуты `_income` и `_position`**

```python
class MyCustomStrategy(StrategyInterface):
    def __init__(self, deposit, percent_from_deposit, items_per_trade):
        self._position = 0
        self._income = 0.0
        # ... остальная инициализация
        
    def execute(self, signal: Signal) -> List[OrderIntent]:
        # Ваша торговая логика
        pass
        
    def close_position(self, candle) -> OrderIntent | None:
        # Логика закрытия позиций
        pass
        
    @property
    def strategy_name(self) -> str:
        return "My Custom Strategy"
```