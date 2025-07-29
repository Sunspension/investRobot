# TinkoffAPIClientable - Примеры использования

## Обзор

`TinkoffAPIClientable` - это интерфейс для работы с Tinkoff Invest API, который обеспечивает полиморфизм и упрощает тестирование торговых стратегий.

## Основные преимущества

- **Полиморфизм**: Один код работает с реальным API и моками
- **Тестируемость**: Легко создавать моки для unit-тестов
- **Типобезопасность**: Полная типизация всех методов
- **Совместимость**: Реализуется как реальным `TinkoffAPIClient`, так и `MockTinkoffAPIClient`

## Примеры использования

### 1. Тестирование торговой стратегии

```python
from robotlib.trading.interfaces import TinkoffAPIClientable
from robotlib.trading.order_executor import OrderResult
from robotlib.utils.logger import get_logger

async def test_trading_strategy(api_client: TinkoffAPIClientable) -> List[OrderResult]:
    """
    Тестирует торговую стратегию с любым API клиентом
    
    Args:
        api_client: API клиент (реальный или мок)
    
    Returns:
        Список результатов ордеров
    """
    logger = get_logger(__name__)
    results = []
    
    async with api_client:
        # Проверяем доступность рынка
        if not await api_client.check_market_availability():
            logger.error("Рынок недоступен")
            return results
        
        logger.info("Рынок доступен, начинаем торговлю")
        
        # Получаем информацию о портфеле
        portfolio = await api_client.get_portfolio()
        logger.info(f"Портфель: {portfolio.total_amount_shares.units} руб")
        
        # Получаем информацию об инструменте
        instrument = await api_client.get_instrument_by_figi("FUTIMOEXF000")
        logger.info(f"Инструмент: {instrument.ticker} - {instrument.name}")
        
        # Размещаем ордера
        orders = [
            ("FUTIMOEXF000", 1, 100.0, "buy", "market"),
            ("FUTIMOEXF000", 1, 105.0, "sell", "limit")
        ]
        
        for figi, quantity, price, direction, order_type in orders:
            result = await api_client.place_order(
                figi=figi,
                quantity=quantity,
                price=price,
                direction=direction,
                order_type=order_type
            )
            results.append(result)
            logger.info(f"Ордер {direction}: {result.success}, ID: {result.order_id}")
        
        # Получаем историю операций
        operations = await api_client.get_operations_history(
            from_date=datetime.now() - timedelta(days=1),
            to_date=datetime.now()
        )
        logger.info(f"Операций в истории: {len(operations.operations)}")
    
    return results
```

### 2. Использование с реальным API

```python
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from config_data.config import load_config

async def main():
    config = load_config()
    
    # Создаем реальный API клиент
    api_client = TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.id,
        sandbox_token=config.tcs_client.sandbox_token
    )
    
    # Тестируем стратегию с реальным API
    results = await test_trading_strategy(api_client)
    print(f"Результат: {len(results)} ордеров")
```

### 3. Использование с мок-клиентом для тестов

```python
from tests.trading_mocks import MockTinkoffAPIClient

async def test_with_mock():
    # Создаем мок-клиент для тестирования
    mock_client = MockTinkoffAPIClient(
        success_rate=0.8,  # 80% успешных операций
        deposit=100000.0   # Начальный депозит
    )
    
    # Тестируем стратегию с моком
    results = await test_trading_strategy(mock_client)
    print(f"Мок-тест: {len(results)} ордеров")
```

### 4. Демонстрация полиморфизма

```python
async def demonstrate_polymorphism():
    """Показывает, как один код работает с разными реализациями"""
    
    clients = [
        ("Реальный API", TinkoffAPIClient(...)),
        ("Мок с ошибками", MockTinkoffAPIClient(success_rate=0.3)),
        ("Мок успешный", MockTinkoffAPIClient(success_rate=1.0))
    ]
    
    for name, client in clients:
        print(f"Тестируем {name}:")
        results = await test_trading_strategy(client)
        print(f"  Результат: {len(results)} ордеров")
```

## Основные методы интерфейса

### Контекстный менеджер
```python
async with api_client:
    # Работа с API
    pass
```

### Проверка рынка
```python
is_available = await api_client.check_market_availability()
```

### Работа с портфелем
```python
portfolio = await api_client.get_portfolio()
positions = await api_client.get_positions()
```

### Размещение ордеров
```python
result = await api_client.place_order(
    figi="FUTIMOEXF000",
    quantity=1,
    price=100.0,
    direction="buy",
    order_type="market"
)
```

### Получение информации об инструментах
```python
instrument = await api_client.get_instrument_by_figi("FUTIMOEXF000")
```

### История операций
```python
operations = await api_client.get_operations_history(
    from_date=start_date,
    to_date=end_date
)
```
