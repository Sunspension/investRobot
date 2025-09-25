from __future__ import annotations

from typing import List, Dict

from robotlib.trading.order_types import OrderIntent, OrderDirection, OrderType
from robotlib.utils.logger import get_logger
from .intent_arbiter_interfaces import IntentArbiterable


class SimpleIntentArbiter(IntentArbiterable):
    """Простой арбитр: неттинг BUY/SELL по FIGI в один итоговый Intent."""

    def __init__(self) -> None:
        self._buffer: List[OrderIntent] = []
        self._logger = get_logger(__name__)

    def add_intents(self, intents: List[OrderIntent]) -> None:
        if not intents:
            return
        self._buffer.extend(intents)

    def flush(self) -> List[OrderIntent]:
        if not self._buffer:
            return []
        per_figi_net: Dict[str, int] = {}
        for it in self._buffer:
            try:
                qty = int(getattr(it, 'quantity', 0) or 0)
                if getattr(it, 'direction', None) == OrderDirection.SELL:
                    qty = -qty
                figi = getattr(it, 'figi', 'unknown') or 'unknown'
                per_figi_net[figi] = per_figi_net.get(figi, 0) + qty
            except Exception:
                continue

        result: List[OrderIntent] = []
        for figi, net in per_figi_net.items():
            if net == 0:
                continue
            direction = OrderDirection.BUY if net > 0 else OrderDirection.SELL
            qty = abs(int(net))
            if qty <= 0:
                continue
            result.append(
                OrderIntent(
                    figi=figi,
                    direction=direction,
                    order_type=OrderType.MARKET,
                    quantity=qty,
                    strategy="arbiter",
                )
            )

        self._buffer.clear()
        return result


