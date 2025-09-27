from __future__ import annotations

import math

from dataclasses import dataclass
from tinkoff.invest import MoneyValue, Quotation


@dataclass(init=False, order=True)
class Money:
    units: int
    nano: int
    MOD: int = 10 ** 9

    def __init__(self, value: None | int | float | Quotation | MoneyValue | Money, nano: int = None):
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
                case Quotation() as value:
                    self.units = value.units
                    self.nano = value.nano
                case MoneyValue() as value:
                    self.units = value.units
                    self.nano = value.nano
                    # Сохраняем информацию о валюте для валютных конвертаций
                    if hasattr(value, 'currency'):
                        self._currency = value.currency
                case Money() as value:
                    self.units = value.units
                    self.nano = value.nano
                case None:
                    # Обработка None значений
                    self.units = 0
                    self.nano = 0
                case _:
                    # Последняя попытка - конвертация в float
                    try:
                        float_val = float(value)
                        self.units = int(math.floor(float_val))
                        self.nano = int((float_val - math.floor(float_val)) * self.MOD)
                    except (TypeError, ValueError):
                        raise ValueError(f'{type(value)} is not supported as initial value for Money')

    def __float__(self):
        return self.units + self.nano / self.MOD

    def to_float(self):
        return float(self)
    
    def to_float_with_currency(self, point_value: float = 1.0) -> float:
        """Конвертирует Money в float с учетом валюты
        
        Args:
            point_value: Коэффициент конвертации для валюты 'pt.' (по умолчанию 1.0)
            
        Returns:
            Float значение с учетом валютной конвертации
        """
        float_value = float(self)
        
        # Если у нас есть информация о валюте, применяем конвертацию
        # Для фьючерсов (currency='pt.') умножаем на point_value
        if hasattr(self, '_currency') and self._currency == 'pt.':
            return float_value * point_value
        
        return float_value

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


def money_value_to_float_with_currency(value: MoneyValue | None, point_value: float = 1.0) -> float:
    """Safely convert MoneyValue to float with currency conversion; returns 0.0 on None.
    
    Args:
        value: MoneyValue to convert
        point_value: Conversion factor for points to rubles (default 1.0 for rubles)
    
    Returns:
        Float value in rubles
    """
    if value is None:
        return 0.0
    
    # Convert to float first
    float_value = float(value.units) + float(value.nano) / Money.MOD
    
    # If currency is points, convert to rubles
    if hasattr(value, 'currency') and value.currency == 'pt.':
        return float_value * point_value
    
    # For rubles and other currencies, return as is
    return float_value


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
