#!/usr/bin/env python3
"""
CLI для операций в песочнице Tinkoff Invest API.

Пример пополнения sandbox-счёта:
  python tools/sandbox_cli.py payin --amount 100000
"""

import asyncio
import argparse
from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient


async def cmd_payin(amount: float) -> int:
    config = load_config()

    if not getattr(config.tcs_client, 'sandbox_token', None):
        print("sandbox_token не задан в конфигурации (.env)")
        return 2

    async with TinkoffAPIClient(
        token=config.tcs_client.token,
        account_id=config.tcs_client.account_id,
        sandbox_token=config.tcs_client.sandbox_token,
    ) as api:
        ok = await api.sandbox_pay_in(amount)
        if ok:
            print(f"Sandbox пополнен на {amount:.2f} RUB")
            return 0
        print("Не удалось пополнить sandbox")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Sandbox CLI (Tinkoff)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_payin = sub.add_parser("payin", help="Пополнить sandbox-счёт в рублях")
    p_payin.add_argument("--amount", type=float, required=True, help="Сумма в RUB")

    args = parser.parse_args()

    if args.command == "payin":
        raise SystemExit(asyncio.run(cmd_payin(args.amount)))


if __name__ == "__main__":
    main()


