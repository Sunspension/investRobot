from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict
import time


class EventType(Enum):
    CANDLE_RECEIVED = "candle_received"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_PLACED = "order_placed"
    ORDER_FILLED = "order_filled"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_UPDATED = "portfolio_updated"
    MARKET_STATUS_CHANGED = "market_status_changed"


@dataclass
class TradingEvent:
    event_type: EventType
    data: Dict[str, Any]
    timestamp: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()

    def __repr__(self) -> str:
        return f"TradingEvent({self.event_type.value}, {self.data})"


