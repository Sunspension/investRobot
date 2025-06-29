import asyncio

from config_data.config import load_config
from tinkoff.invest import AsyncClient, MoneyValue

config = load_config()
token = config.tcs_client.token
account_id = config.tcs_client.id
sandbox_token = config.tcs_client.sandbox

class AccountHelper:
    @staticmethod
    async def create_sandbox_account(client: AsyncClient):
        account = await client.sandbox.open_sandbox_account()
        print(f"Создан песочный счёт: {account.account_id}")
        return account
    
    @staticmethod
    async def topup_account(client: AsyncClient, account_id: str, amount: int):
        money = MoneyValue(currency="RUB", units=amount, nano=0)
        response = await client.sandbox.sandbox_pay_in(account_id=account_id, amount=money)
        print(f"Счет пополнен, текущий баланс: {response.balance.units} руб.")

async def main():
    async with AsyncClient(sandbox_token) as client:
        response = await client.sandbox.get_sandbox_accounts()
        if len(response.accounts) == 0:
            await AccountHelper.create_sandbox_account(client)
        else:
            account_id = response.accounts[0].id
            portfolio = await client.sandbox.get_sandbox_portfolio(account_id=account_id)
            print(f"Баланс на счёте {account_id}: {portfolio.total_amount_portfolio.units} рублей")
            # await AccountHelper.topup_account(client=client, account_id=account_id, amount=1000000)


if __name__ == "__main__":
    asyncio.run(main())