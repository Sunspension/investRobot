# save as tools/manual_sber_trade.py
import asyncio
from datetime import datetime
from typing import Dict, Any
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config_data.config import load_config
from robotlib.trading.tinkoff_api_client import TinkoffAPIClient
from robotlib.utils.sql_repository import insert_orders

SBER_FIGI = "BBG004730N88"  # SBER

async def _record_order(
    db_path: str,
    *,
    account_id: str | None,
    figi: str,
    side: str,  # 'buy' | 'sell'
    price: float,
    quantity: int,
    order_id: str | None = None,
    reason: str = "manual",
) -> None:
    order: Dict[str, Any] = {
        "order_id": order_id,
        "account_id": account_id,
        "figi": figi,
        "time": datetime.now(),
        "type": side,
        "price": float(price),
        "quantity": int(quantity),
        "status": "filled",
        "commission": 0.0,
        "strategy": "manual",
        "reason": reason,
    }
    await insert_orders(db_path, [order])

async def main(
    figi: str = SBER_FIGI,
    qty: int = 1,
    db_path: str = "data/market.db",
) -> None:
    cfg = load_config()
    async with TinkoffAPIClient(
        token=cfg.tcs_client.token,
        account_id=cfg.tcs_client.account_id,
        sandbox_token=cfg.tcs_client.sandbox_token,
    ) as api:
        # BUY
        buy = await api.buy_market(figi=figi, quantity=qty, wait_execution=True)
        if not buy.success:
            print(f"BUY rejected: {getattr(buy, 'error_message', 'unknown')}")
            return
        print(f"BUY filled: qty={buy.executed_quantity} price={buy.executed_price}")
        await _record_order(
            db_path,
            account_id=getattr(api, "account_id", None),
            figi=figi,
            side="buy",
            price=buy.executed_price or 0.0,
            quantity=buy.executed_quantity or qty,
            order_id=getattr(buy, "order_id", None),
            reason="manual buy",
        )

        # SELL
        sell = await api.sell_market(figi=figi, quantity=qty, wait_execution=True)
        if not sell.success:
            print(f"SELL rejected: {getattr(sell, 'error_message', 'unknown')}")
            return
        print(f"SELL filled: qty={sell.executed_quantity} price={sell.executed_price}")
        await _record_order(
            db_path,
            account_id=getattr(api, "account_id", None),
            figi=figi,
            side="sell",
            price=sell.executed_price or 0.0,
            quantity=sell.executed_quantity or qty,
            order_id=getattr(sell, "order_id", None),
            reason="manual sell",
        )

if __name__ == "__main__":
    asyncio.run(main())