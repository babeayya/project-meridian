from decimal import Decimal

import pytest

from app.domain.calc.units import Money, UnitError


def test_scale_normalization_inr_crore():
    m = Money(Decimal("1250"), "INR", "crore")
    assert m.base_amount == Decimal("12500000000")
    assert m.to_scale("million").amount == Decimal("12500")


def test_currency_mismatch_raises():
    usd = Money(Decimal("100"), "USD", "million")
    inr = Money(Decimal("100"), "INR", "crore")
    with pytest.raises(UnitError, match="Currency mismatch"):
        _ = usd + inr


def test_float_amount_rejected():
    with pytest.raises(UnitError, match="Decimal"):
        Money(1.5, "USD")  # type: ignore[arg-type]


def test_float_multiplication_rejected():
    m = Money(Decimal("10"), "USD")
    with pytest.raises(UnitError):
        _ = m * 1.1  # type: ignore[operator]


def test_addition_across_scales_same_currency():
    total = Money(Decimal("1"), "USD", "billion") + Money(Decimal("500"), "USD", "million")
    assert total.base_amount == Decimal("1500000000")


def test_ratio_is_dimensionless():
    debt = Money(Decimal("40"), "USD", "billion")
    equity = Money(Decimal("160"), "USD", "billion")
    assert debt.ratio(equity) == Decimal("0.25")
