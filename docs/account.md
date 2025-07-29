# 🏦 Управление аккаунтами

Модуль `account.py` предоставляет удобные инструменты для работы с песочными счетами Тинькофф Инвестиций.

## 📋 Содержание

- [Обзор](#обзор)
- [Класс AccountHelper](#класс-accounthelper)
- [Методы](#методы)
- [Примеры использования](#примеры-использования)
- [Настройка](#настройка)

## 🎯 Обзор

Файл `account.py` содержит класс `AccountHelper` с методами для:
- Создания новых песочных счетов
- Пополнения существующих счетов
- Управления тестовыми аккаунтами

> **Важно**: Этот модуль работает только с песочными счетами (sandbox), не с реальными деньгами!

## 🏗️ Класс AccountHelper

### Инициализация

```python
from account import AccountHelper
```

Класс содержит только статические методы, поэтому не требует создания экземпляра.

## 🔧 Методы

### `create_sandbox_account(client: AsyncClient)`

Создает новый песочный счет в Тинькофф Инвестициях.

**Параметры:**
- `client` (AsyncClient) - клиент Tinkoff API

**Возвращает:**
- `account` - объект созданного счета с полем `account_id`

**Пример:**
```python
async with AsyncClient(token=sandbox_token) as client:
    account = await AccountHelper.create_sandbox_account(client)
    print(f"ID нового счета: {account.account_id}")
```

### `topup_account(client: AsyncClient, account_id: str, amount: int)`

Пополняет указанный песочный счет на заданную сумму.

**Параметры:**
- `client` (AsyncClient) - клиент Tinkoff API
- `account_id` (str) - идентификатор счета
- `amount` (int) - сумма пополнения в рублях

**Пример:**
```python
await AccountHelper.topup_account(client, "account_123", 100000)
# Пополняет счет на 100,000 рублей
```

## 📝 Примеры использования

### Базовое использование

```python
import asyncio
from tinkoff.invest import AsyncClient
from account import AccountHelper
from config_data.config import load_config

async def setup_test_account():
    config = load_config()
    
    async with AsyncClient(token=config.tcs_client.sandbox_token) as client:
        # Создаем новый счет
        account = await AccountHelper.create_sandbox_account(client)
        
        # Пополняем его
        await AccountHelper.topup_account(client, account.account_id, 50000)
        
        return account.account_id

# Запуск
account_id = asyncio.run(setup_test_account())
```

### Создание нескольких счетов

```python
async def create_multiple_accounts():
    config = load_config()
    
    async with AsyncClient(token=config.tcs_client.sandbox_token) as client:
        accounts = []
        
        for i in range(3):
            account = await AccountHelper.create_sandbox_account(client)
            await AccountHelper.topup_account(client, account.account_id, 100000)
            accounts.append(account.account_id)
            
        return accounts
```

### Интеграция с торговой системой

```python
from robotlib.trading.trading_session import TradingSession, TradingConfig

async def setup_trading_account():
    config = load_config()
    
    async with AsyncClient(token=config.tcs_client.sandbox_token) as client:
        # Создаем счет для торговли
        account = await AccountHelper.create_sandbox_account(client)
        await AccountHelper.topup_account(client, account.account_id, 200000)
        
        # Настраиваем торговую сессию
        trading_config = TradingConfig(
            account_id=account.account_id,
            sandbox_token=config.tcs_client.sandbox_token,
            # ... другие параметры
        )
        
        return trading_config
```

## ⚙️ Настройка

### Конфигурация

Модуль использует конфигурацию из `config_data/config.py`:

```python
config = load_config()
sandbox_token = config.tcs_client.sandbox_token  # Токен песочницы
```

### Требования

- Токен песочницы Тинькофф Инвестиций
- Установленный пакет `tinkoff-investments`
- Настроенный файл конфигурации

## 🚀 Запуск

Для тестирования модуля:

```bash
python account.py
```

Это создаст новый песочный счет и пополнит его на 100,000 рублей.

## ⚠️ Важные замечания

1. **Только песочница**: Все операции выполняются только с тестовыми счетами
2. **Лимиты**: У песочных счетов могут быть ограничения на количество операций
3. **Время жизни**: Песочные счета могут автоматически удаляться через определенное время
4. **Безопасность**: Никогда не используйте реальные токены в тестовом коде

## 🔗 Связанные модули

- [Торговая система](trading.md) - использование созданных счетов для торговли
- [Конфигурация](../config_data/config.py) - настройка токенов и параметров
- [Tinkoff API](https://tinkoff.github.io/investAPI/) - официальная документация API

## 📞 Поддержка

При возникновении проблем:
1. Проверьте правильность токена песочницы
2. Убедитесь, что у вас есть доступ к Tinkoff API
3. Проверьте логи на наличие ошибок подключения
