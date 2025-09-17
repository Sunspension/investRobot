"""
Типы данных для торговых ордеров
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


class OrderDirection(Enum):
    """Направление ордера"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Тип ордера"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Статус ордера"""
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"


@dataclass
class OrderIntent:
    """Намерение на выполнение ордера"""
    figi: str
    direction: OrderDirection
    order_type: OrderType
    quantity: int
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"  # Good Till Cancelled
    client_order_id: Optional[str] = None


@dataclass
class OrderExecution:
    """Результат выполнения ордера"""
    order_id: str
    figi: str
    direction: OrderDirection
    quantity: int
    filled_quantity: int
    price: float
    status: OrderStatus
    timestamp: datetime
    error_message: Optional[str] = None
    commission: float = 0.0
    reason: Optional[str] = None
