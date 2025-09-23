"""
Модуль для управления песочными счетами Тинькофф Инвестиций.

Предоставляет удобные методы для создания и пополнения тестовых счетов.
Все операции выполняются только с песочными счетами (sandbox), не с реальными деньгами.
"""

import asyncio
import sys
import os

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_data.config import load_config
from tinkoff.invest import AsyncClient, MoneyValue

# Загружаем конфигурацию
config = load_config()
token = config.tcs_client.token
account_id = config.tcs_client.account_id
sandbox_token = config.tcs_client.sandbox_token

class AccountHelper:
    """Вспомогательный класс для работы с песочными счетами."""
    
    @staticmethod
    async def create_sandbox_account(client: AsyncClient):
        """
        Создает новый песочный счет.
        
        Args:
            client (AsyncClient): Клиент Tinkoff API
            
        Returns:
            account: Объект созданного счета с полем account_id
        """
        account = await client.sandbox.open_sandbox_account()
        print(f"Создан песочный счёт: {account.account_id}")
        return account
    
    @staticmethod
    async def topup_account(client: AsyncClient, account_id: str, amount: int):
        """
        Пополняет указанный песочный счет на заданную сумму.
        
        Args:
            client (AsyncClient): Клиент Tinkoff API
            account_id (str): Идентификатор счета
            amount (int): Сумма пополнения в рублях
        """
        money = MoneyValue(currency="RUB", units=amount, nano=0)
        await client.sandbox.sandbox_pay_in(account_id=account_id, amount=money)
        print(f"Пополнен счёт {account_id} на {amount} рублей")

async def main():
    """Пример использования AccountHelper для создания и пополнения счета."""
    async with AsyncClient(token=sandbox_token) as client:
        # Создаем песочный счёт
        account = await AccountHelper.create_sandbox_account(client)
        
        # Пополняем счёт на 100,000 рублей
        await AccountHelper.topup_account(client, account.account_id, 100000)

if __name__ == "__main__":
    # Запуск примера при выполнении файла напрямую
    asyncio.run(main())
