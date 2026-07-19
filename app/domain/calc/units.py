"""Typed money: currency + scale safety.

Mixing INR crore with USD millions must fail at construction/operation time,
never silently produce a wrong valuation.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


class UnitError(ValueError):
    pass


# multiplier to convert one unit of the scale into base currency units
SCALES: dict[str, Decimal] = {
    "unit": Decimal(1),
    "thousand": Decimal(1_000),
    "lakh": Decimal(100_000),
    "million": Decimal(1_000_000),
    "crore": Decimal(10_000_000),
    "billion": Decimal(1_000_000_000),
}


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str            # ISO 4217, e.g. "USD", "INR"
    scale: str = "unit"

    def __post_init__(self) -> None:
        if self.scale not in SCALES:
            raise UnitError(f"Unknown scale '{self.scale}'")
        if not isinstance(self.amount, Decimal):
            raise UnitError("Money.amount must be Decimal (never float)")

    @property
    def base_amount(self) -> Decimal:
        """Amount expressed in base currency units (scale-normalized)."""
        return self.amount * SCALES[self.scale]

    def to_scale(self, scale: str) -> Money:
        if scale not in SCALES:
            raise UnitError(f"Unknown scale '{scale}'")
        return Money(self.base_amount / SCALES[scale], self.currency, scale)

    def _check(self, other: Money) -> None:
        if not isinstance(other, Money):
            raise UnitError(f"Cannot combine Money with {type(other).__name__}")
        if other.currency != self.currency:
            raise UnitError(
                f"Currency mismatch: {self.currency} vs {other.currency} — convert first"
            )

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.base_amount + other.base_amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.base_amount - other.base_amount, self.currency)

    def __mul__(self, factor: Decimal | int) -> Money:
        if isinstance(factor, float):
            raise UnitError("Multiply Money by Decimal or int, not float")
        return Money(self.base_amount * Decimal(factor), self.currency)

    def ratio(self, other: Money) -> Decimal:
        """Dimensionless ratio of two like-currency amounts."""
        self._check(other)
        if other.base_amount == 0:
            raise UnitError("Division by zero Money")
        return self.base_amount / other.base_amount
