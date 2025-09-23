# Торговая система

Система для реальной торговли на Московской бирже через Tinkoff API.

## 🏗️ Архитектура

### Основные компоненты:

1. **MarketHours** - проверка торговых часов биржи
2. **OrderExecutor** - выполнение торговых приказов
3. **PortfolioManager** - управление портфелем и позициями
4. **RiskManager** - контроль рисков
5. **TradingSession** - основная торговая сессия

## 🚀 Быстрый старт

### 1. Запуск в песочнице (рекомендуется для тестирования):

```bash
python main_trading.py --figi FUTIMOEXF000 --deposit 50000 --percent-from-deposit 40
```

#### Пополнение sandbox и пример покупки через API

```python
from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient

config = load_config()

async with TinkoffAPIClient(
    token=config.tcs_client.token,
    account_id=config.tcs_client.account_id,
    sandbox_token=config.tcs_client.sandbox_token,
) as api:
    # Пополнить sandbox на 100 000 RUB
    await api.sandbox_pay_in(100000.0)

    # Рыночная покупка 1 лота
    res = await api.buy_market(figi="FUTIMOEXF000", quantity=1, wait_execution=True)
    print(res)
```

### 2. Запуск с кастомными параметрами:

```bash
python main_trading.py \
  --figi FUTIMOEXF000 \
  --deposit 100000 \
  --percent-from-deposit 50 \
  --items-per-trade 5 \
  --macd-fast 10 \
  --macd-slow 15 \
  --macd-signal 11 \
  --max-position-size 50000 \
  --max-daily-loss 2500 \
  --stop-loss-percent 3 \
  --take-profit-percent 8
```

### 3. Реальная торговля (осторожно!):

```bash
python main_trading.py --live-trading --figi FUTIMOEXF000
```

## 📊 Параметры

### Основные параметры:
- `--figi` - FIGI инструмента (по умолчанию FUTIMOEXF000)
- `--deposit` - размер депозита в рублях
- `--percent-from-deposit` - процент от депозита для торговли
- `--items-per-trade` - количество лотов за сделку

### Параметры стратегии:
- `--macd-fast` - период быстрой EMA для MACD
- `--macd-slow` - период медленной EMA для MACD
- `--macd-signal` - период сигнальной линии MACD
- `--atr-period` - период для ATR
- `--lookback-min/max` - диапазон поиска пиков
- `--peak-prominence` - минимальная значимость пика

### Лимиты риска:
- `--max-position-size` - максимальный размер позиции в рублях
- `--max-daily-loss` - максимальная дневная потеря в рублях
- `--max-portfolio-risk` - максимальный риск портфеля в %
- `--max-single-trade` - максимальный размер одной сделки
- `--stop-loss-percent` - стоп-лосс в процентах
- `--take-profit-percent` - тейк-профит в процентах

### Настройки торговли:
- `--live-trading` - реальная торговля (по умолчанию песочница)
- `--auto-close-positions` - автоматически закрывать позиции в конце дня
- `--force-start` - принудительный запуск даже если рынок закрыт

## 🛡️ Управление рисками

### Автоматические проверки:
1. **Торговые часы** - торговля только в рабочее время биржи
2. **Размер позиции** - контроль максимального размера позиции
3. **Дневные убытки** - остановка торговли при превышении лимита
4. **Риск портфеля** - контроль общего риска портфеля
5. **Стоп-лосс** - автоматическое закрытие убыточных позиций
6. **Тейк-профит** - уведомления о достижении целевой прибыли

### Рекомендуемые настройки риска:

#### Консервативные:
```bash
--max-position-size 20000 \
--max-daily-loss 1000 \
--max-portfolio-risk 10 \
--stop-loss-percent 2 \
--take-profit-percent 4
```

#### Умеренные:
```bash
--max-position-size 50000 \
--max-daily-loss 2500 \
--max-portfolio-risk 15 \
--stop-loss-percent 3 \
--take-profit-percent 8
```

#### Агрессивные:
```bash
--max-position-size 100000 \
--max-daily-loss 5000 \
--max-portfolio-risk 25 \
--stop-loss-percent 5 \
--take-profit-percent 15
```

## 📈 Мониторинг

### Логирование:
- Все операции логируются в файл `trading_YYYYMMDD_HHMMSS.log`
- Консольный вывод с уровнем INFO
- Детальная статистика сессии

### Статистика:
- Количество сигналов
- Выполненные сделки
- Процент успешных сделок
- Общий PnL
- Время работы сессии

## ⚠️ Важные предупреждения

1. **Всегда тестируйте в песочнице** перед реальной торговлей
2. **Начинайте с малых сумм** для проверки стратегии
3. **Мониторьте работу робота** - не оставляйте без присмотра
4. **Устанавливайте разумные лимиты риска**
5. **Регулярно анализируйте результаты** и корректируйте параметры

## 🔧 Настройка

### Конфигурация API:
Убедитесь, что в `config_data/config.py` правильно настроены:
- `tcs_client.token` - токен доступа к API
 - `tcs_client.account_id` - ID торгового счета
- `tcs_client.sandbox_token` - токен песочницы

### Торговые часы:
Система автоматически проверяет торговые часы Московской биржи:

**Будни (понедельник - пятница):**
- Аукцион открытия: 9:50 - 10:00 МСК
- Основная сессия: 10:00 - 18:50 МСК
- Вечерняя сессия: 19:05 - 23:50 МСК

**Выходные (суббота и воскресенье):**
- Аукцион открытия: 9:50 - 10:00 МСК
- Утренняя сессия: 10:00 - 14:00 МСК
- Вечерняя сессия: 19:05 - 23:50 МСК

> **Особенность Тинькофф**: Торговля фьючерсами и некоторыми акциями доступна в выходные дни!

## 📝 Примеры использования

### Простой запуск:
```bash
python example_trading.py
```

### Кастомная конфигурация:
```python
from robotlib.trading import TradingSession, TradingConfig, RiskLimits

# Создаем конфигурацию
config = TradingConfig(
    figi="FUTIMOEXF000",
    deposit=100000,
    percent_from_deposit=50,
    items_per_trade=5,
    signal_manager_params={
        'macd_fast': 10,
        'macd_slow': 15,
        'macd_signal': 11,
        # ... другие параметры
    },
    risk_limits=RiskLimits(
        max_daily_loss=2500,
        max_position_size=50000,
        percent_from_deposit=50,
        items_per_trade=20,
        stop_loss_threshold=8
    ),
    sandbox=True
)

# Запускаем сессию
session = TradingSession(config, token, account_id)
await session.start()
await session.run_trading_loop()
```

## 🆘 Поддержка

При возникновении проблем:
1. Проверьте логи в файле `trading_*.log`
2. Убедитесь в правильности настроек API
3. Проверьте торговые часы
4. Начните с песочницы для отладки
