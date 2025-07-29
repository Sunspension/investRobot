# 🚀 InvestRobot - Алгоритмический торговый робот

**InvestRobot** - это современный робот для алгоритмической торговли на Московской бирже через Tinkoff Invest API.

## ✨ Основные возможности

* 🤖 **Автоматическая торговля** фьючерсами и акциями
* 📊 **Бэктестинг стратегий** с оптимизацией параметров
* 🎯 **Реальная торговля** с проверкой торговых часов
* 📈 **Визуализация** результатов торговли
* 🔧 **Модульная архитектура** стратегий
* 📝 **Подробное логирование** всех операций

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации
Создайте файл `.env` с вашими токенами:
```env
TINKOFF_TOKEN=your_token_here
TINKOFF_ACCOUNT=your_account_id
SANDBOX_TOKEN=your_sandbox_token
```

### 3. Запуск
```bash
# Бэктестинг и оптимизация
python scripts/main_stats.py optimize --db ./data/market.db --figi FUTIMOEXF000

# Реальная торговля
python scripts/main_trading.py --live-trading

# Визуализация
python scripts/main.py
```

## 📚 Документация

- [📋 Правила разработки](project_rules.md) - **ОБЯЗАТЕЛЬНО К ПРОЧТЕНИЮ**
- [Быстрый старт торговой системы](trading_quick_start.md)
- [Полная документация торговли](trading.md)
- [Торговые часы](trading_hours.md)
- [Документация стратегий](strategy_interface.md)
- [Управление аккаунтами](account.md)
- [Использование TinkoffAPIClientable](tinkoff_api_interface_usage.md)


## 🏗️ Архитектура проекта

### Основные компоненты

#### 📊 **Бэктестинг и оптимизация**
- `scripts/main_stats.py` - CLI для загрузки данных и оптимизации параметров
- `robotlib/utils/backtest_sqlite.py` - бэктестинг с SQLite
- `robotlib/utils/param_search.py` - оптимизация параметров стратегий
- `robotlib/utils/candles_loader.py` - загрузка исторических данных

#### 🤖 **Торговая система**
- `scripts/main_trading.py` - запуск реальной торговли
- `robotlib/trading/` - модули торговой системы:
  - `trading_session.py` - управление торговыми сессиями
  - `order_executor.py` - выполнение ордеров
  - `portfolio_manager.py` - управление портфелем
  - `risk_manager.py` - контроль рисков

#### 📈 **Стратегии**
- `robotlib/strategies/` - торговые стратегии:
  - `strategy_interface.py` - базовый интерфейс стратегий
  - `long.py` - стратегия покупки
  - `short.py` - стратегия продажи
  - `strategy_manager.py` - управление стратегиями

#### 🛠️ **Утилиты**
- `robotlib/utils/market_hours.py` - проверка торговых часов
- `robotlib/utils/money.py` - работа с денежными суммами
- `robotlib/utils/visualizator.py` - визуализация данных
- `scripts/account.py` - управление песочными счетами

#### 📁 **Данные и логи**
- `data/` - база данных и результаты оптимизации
- `logs/` - файлы логов
- `examples/` - примеры использования

## 📖 Дополнительная документация

- [Модуль money](money.md) - работа с денежными типами
- [Модуль visualizer](visualizer.md) - визуализация торговых данных