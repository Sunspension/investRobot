from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid
from typing import Optional
import asyncio

from tinkoff.invest import (
    OrderDirection,
    OrderType,
    PostOrderRequest,
    CancelOrderRequest,
    OrderState,
)
from robotlib.utils.money import money_value_to_float_with_currency
from tinkoff.invest.schemas import MoneyValue
from robotlib.utils.money import Money


@dataclass
class OrderResult:
    success: bool
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    executed_price: Optional[float] = None
    executed_quantity: Optional[int] = None
    commission: Optional[float] = None
    order_status: Optional[str] = None
    is_executed: bool = False


def float_to_money_value(value: float) -> MoneyValue:
    return MoneyValue(currency="rub", units=int(value), nano=int((value - int(value)) * 1_000_000_000))


async def place_order(client, figi: str, direction: OrderDirection, quantity: int, price: Optional[float], order_type: OrderType) -> OrderResult:
    client_order_id = str(uuid.uuid4())
    if client._sandbox_token:  # noqa: SLF001
        await client._limiter_post.acquire()  # noqa: SLF001
        response = await client._services.sandbox.post_sandbox_order(  # noqa: SLF001
            figi=figi,
            quantity=quantity,
            price=float_to_money_value(price) if price else None,
            direction=direction,
            account_id=client._account_id,  # noqa: SLF001
            order_type=order_type,
            order_id=client_order_id,
        )
    else:
        request = PostOrderRequest(
            figi=figi,
            quantity=quantity,
            price=float_to_money_value(price) if price else None,
            direction=direction,
            account_id=client._account_id,  # noqa: SLF001
            order_type=order_type,
            order_id=client_order_id,
        )
        await client._limiter_post.acquire()  # noqa: SLF001
        response = await client._services.orders.post_order(request)  # noqa: SLF001

    if getattr(response, "order_id", None):
        # Для рыночных ордеров не возвращаем цену, так как она будет получена в wait_for_order_execution
        # Для лимитных ордеров возвращаем переданную цену
        executed_price = price if order_type == OrderType.ORDER_TYPE_LIMIT else None
        return OrderResult(success=True, order_id=response.order_id, executed_price=executed_price, executed_quantity=quantity)
    # Если ответа нет или нет order_id, пробуем вытащить сообщение из метаданных/исключения (для песочницы обычно None)
    return OrderResult(success=False, error_message="Не удалось получить ID приказа")


async def get_order_status(client, order_id: str) -> Optional[OrderState]:
    try:
        if client._sandbox_token:  # noqa: SLF001
            await client._limiter_get.acquire()  # noqa: SLF001
            return await client._services.sandbox.get_sandbox_order_state(  # noqa: SLF001
                account_id=client._account_id,
                order_id=order_id,
            )
        else:
            await client._limiter_get.acquire()  # noqa: SLF001
            return await client._services.orders.get_order_state(  # noqa: SLF001
                account_id=client._account_id,
                order_id=order_id,
            )
    except Exception:
        return None


async def wait_for_order_execution(client, order_id: str, figi: str = None, *, max_wait_time: int = 30, check_interval: float = 1.0) -> OrderResult:
    start = asyncio.get_running_loop().time()
    while asyncio.get_running_loop().time() - start < max_wait_time:
        state = await get_order_status(client, order_id)
        if not state:
            await asyncio.sleep(check_interval)
            continue
        status = getattr(state, "execution_report_status", "")
        if status == "EXECUTION_REPORT_STATUS_FILL":
            # Получаем point_value для правильной конвертации валюты
            point_value = 1.0
            if figi:
                try:
                    margin_info = await client.get_futures_margin(figi)
                    if margin_info and 'min_price_increment' in margin_info and 'min_price_increment_amount' in margin_info:
                        min_price_increment = margin_info['min_price_increment']
                        min_price_increment_amount = margin_info['min_price_increment_amount']
                        if min_price_increment > 0:
                            point_value = min_price_increment_amount / min_price_increment
                except Exception:
                    point_value = 10.0  # Значение по умолчанию для фьючерса на MOEX
            
            # Конвертируем цены с учетом валюты (единый стиль через Money)
            executed_price = Money(state.executed_order_price).to_float_with_currency(point_value)
            commission = Money(state.initial_commission).to_float_with_currency(point_value)
            
            return OrderResult(
                success=True,
                order_id=order_id,
                executed_price=executed_price,
                executed_quantity=state.lots_executed,
                commission=commission,
                order_status="FILL",
                is_executed=True,
            )
        if status == "EXECUTION_REPORT_STATUS_CANCELLED":
            return OrderResult(success=False, order_id=order_id, error_message="Приказ отменен", order_status="CANCELLED")
        if status == "EXECUTION_REPORT_STATUS_REJECTED":
            return OrderResult(success=False, order_id=order_id, error_message="Приказ отклонен", order_status="REJECTED")
        await asyncio.sleep(check_interval)
    return OrderResult(success=False, order_id=order_id, error_message=f"Таймаут ожидания исполнения приказа (>{max_wait_time}с)", order_status="TIMEOUT")


async def cancel_order(client, order_id: str) -> bool:
    req = CancelOrderRequest(account_id=client._account_id, order_id=order_id)  # noqa: SLF001
    try:
        if client._sandbox_token:  # noqa: SLF001
            await client._limiter_post.acquire()  # noqa: SLF001
            await client._services.sandbox.cancel_sandbox_order(account_id=client._account_id, order_id=order_id)  # noqa: SLF001
        else:
            await client._limiter_post.acquire()  # noqa: SLF001
            await client._services.orders.cancel_order(req)  # noqa: SLF001
        return True
    except Exception:
        return False





