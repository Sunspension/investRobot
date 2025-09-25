from __future__ import annotations

from typing import Protocol, List, Optional
from robotlib.trading.order_types import OrderIntent


class IntentArbiterable(Protocol):
    """Протокол арбитра намерений per-FIGI."""

    def add_intents(self, intents: List[OrderIntent]) -> None:
        """Добавляет порцию intents в текущий буфер."""
        ...

    def flush(self) -> List[OrderIntent]:
        """Выполняет неттинг per-FIGI и возвращает итоговые intents, очищая буфер."""
        ...


