"""
Перечисления для торговой системы.
"""
from enum import Enum


class OperationType(Enum):
    """Тип операции с позицией."""
    OPEN = "open"
    CLOSE = "close"
    INCREASE = "increase"


class PositionDirection(Enum):
    """Направление позиции."""
    LONG = "long"
    SHORT = "short"


