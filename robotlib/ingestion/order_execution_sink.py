from __future__ import annotations

from typing import Any

from robotlib.utils.logger import get_logger
from robotlib.utils.sql_schema import init_db
from robotlib.utils.sql_repository import insert_orders, outbox_enqueue_order
from robotlib.trading_interfaces import OrderEventSinkable
from robotlib.trading.order_types import OrderExecution, OrderIntent


class OrderExecutionSink(OrderEventSinkable):
    """Приёмник для сохранения исполненных ордеров в SQLite.

    Специализируется только на ордерах. Игнорирует все остальные события.
    """

    def __init__(
        self,
        *,
        db_path: str,
        figi: str,
    ) -> None:
        self._logger = get_logger(__name__)
        self._db_path = db_path
        self._figi = figi


    async def on_order_execution(self, execution: OrderExecution, intent: OrderIntent) -> None:
        """Сохраняет исполненные ордера в базу данных."""
        try:
            # Гарантируем наличие схемы БД
            await init_db(self._db_path)
            
            # Преобразуем OrderExecution и OrderIntent в формат для БД
            order_record = {
                'order_id': execution.order_id,
                'account_id': getattr(execution, 'account_id', None),
                'figi': intent.figi,
                'time': execution.timestamp,
                'type': 'buy' if intent.direction.name.lower() == 'buy' else 'sell',
                'price': execution.price or 0.0,
                'quantity': execution.filled_quantity or intent.quantity,
                'status': 'filled' if execution.status.name == 'FILLED' else 'cancelled',
                'commission': execution.commission or 0.0,
                'strategy': getattr(intent, 'strategy', None),
                'reason': execution.reason,
            }
            
            await insert_orders(self._db_path, [order_record])
            
            try:
                self._logger.info(
                    f"Ордер записан в БД: id={order_record['order_id']} "
                    f"type={order_record['type']} price={order_record['price']} "
                    f"qty={order_record['quantity']}"
                )
            except Exception:
                pass
                
            # Пишем в outbox событие для идемпотентной доставки
            try:
                await outbox_enqueue_order(
                    self._db_path,
                    account_id=order_record.get('account_id'),
                    figi=order_record.get('figi'),
                    order_id=order_record.get('order_id'),
                    payload=order_record,
                )
            except Exception as e:
                self._logger.warning(f"Не удалось записать событие в outbox: {e}")
                
        except Exception as e:
            self._logger.warning(f"Не удалось сохранить ордер: {e}")

