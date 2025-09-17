from __future__ import annotations

import math

from dataclasses import dataclass
from tinkoff.invest import MoneyValue, Quotation


@dataclass(init=False, order=True)
class Money:
    units: int
    nano: int
    MOD: int = 10 ** 9

    def __init__(self, value: int | float | Quotation | MoneyValue | Money, nano: int = None):
        if nano:
            assert isinstance(value, int), 'if nano is present, value must be int'
            assert isinstance(nano, int), 'nano must be int'
            self.units = value
            self.nano = nano
        else:
            match value:
                case int() as value:
                    self.units = value
                    self.nano = 0
                case float() as value:
                    self.units = int(math.floor(value))
                    self.nano = int((value - math.floor(value)) * self.MOD)
                case Quotation() | MoneyValue() as value:
                    self.units = value.units
                    self.nano = value.nano
                case Money() as value:
                    self.units = value.units
                    self.nano = value.nano
                case _:
                    raise ValueError(f'{type(value)} is not supported as initial value for Money')

    def __float__(self):
        return self.units + self.nano / self.MOD

    def to_float(self):
        return float(self)

    @classmethod
    def from_float(cls, value: float) -> Money:
        """Создает Money из float значения"""
        return cls(value)

    def to_quotation(self):
        return Quotation(self.units, self.nano)

    def to_money_value(self, currency: str):
        return MoneyValue(currency, self.units, self.nano)

    def __add__(self, other: Money) -> Money:
        return Money(
            self.units + other.units + (self.nano + other.nano) // self.MOD,
            (self.nano + other.nano) % self.MOD
        )

    def __neg__(self) -> Money:
        return Money(-self.units, -self.nano)

    def __sub__(self, other: Money) -> Money:
        return self + -other

    def __mul__(self, other: int) -> Money:
        return Money(self.units * other + (self.nano * other) // self.MOD, (self.nano * other) % self.MOD)

    def __str__(self) -> str:
        return f'<Money units={self.units} nano={self.nano}>'


# --- Helpers for MoneyValue conversions (shared across the project) ---
def money_value_to_float(value: MoneyValue | None) -> float:
    """Safely convert MoneyValue to float; returns 0.0 on None."""
    if value is None:
        return 0.0
    return float(value.units) + float(value.nano) / Money.MOD


def float_to_money_value(
    amount: float,
    *,
    currency: str = "rub",
) -> MoneyValue:
    """Convert float to MoneyValue with given currency.
    Uses truncation toward zero for compatibility with legacy expectations.
    """
    units = int(amount)  # truncates toward zero (e.g., -100.5 -> -100)
    nano = int((amount - units) * Money.MOD)
    return MoneyValue(currency=currency, units=units, nano=nano)
