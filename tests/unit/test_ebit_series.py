"""EBIT reconstruction for filers with no operating-income line.

Banks and insurers never tag us-gaap:OperatingIncomeLoss, which left the
margin history empty and dropped the DCF onto its 12% placeholder. Interest
is a cost of revenue for a lender, so it must not be added back — and the
sector hint alone cannot be trusted, since freshly-resolved companies (JPM
included) carry a null sector.
"""
from datetime import date
from decimal import Decimal

from app.domain.statements.history import FinancialHistory, PeriodFinancials
from app.services.valuation_service import ValuationService


def _history(**series: dict[int, str]) -> FinancialHistory:
    years = sorted({fy for s in series.values() for fy in s})
    return FinancialHistory(currency="USD", annual=[
        PeriodFinancials(
            fiscal_year=fy, period_end=date(fy, 12, 31), currency="USD",
            items={k: Decimal(s[fy]) for k, s in series.items() if fy in s},
        )
        for fy in years
    ])


def _margins(history: FinancialHistory, lender: bool) -> tuple[list, str]:
    ser, basis = ValuationService._ebit_series(history, lender)
    rev = dict(history.series("revenue"))
    return [(ebit / rev[fy]).quantize(Decimal("0.01"))
            for fy, ebit in ser if fy in rev], basis


def test_reported_operating_income_is_used_verbatim():
    h = _history(
        revenue={2023: "1000", 2024: "1100"},
        operating_income={2023: "200", 2024: "275"},
        pretax_income={2023: "150", 2024: "165"},
        interest_expense={2023: "50", 2024: "55"},
    )
    margins, basis = _margins(h, False)
    assert basis == "EBIT"
    assert margins == [Decimal("0.20"), Decimal("0.25")]


def test_industrial_without_operating_line_adds_interest_back():
    """EBIT = pre-tax + interest for a normal borrower."""
    h = _history(
        revenue={2023: "1000", 2024: "1000"},
        pretax_income={2023: "150", 2024: "150"},
        interest_expense={2023: "50", 2024: "50"},
    )
    margins, basis = _margins(h, False)
    assert "pre-tax + interest" in basis
    assert margins == [Decimal("0.20"), Decimal("0.20")]


def test_lender_flag_suppresses_the_add_back():
    """Interest is a cost of revenue for a lender, so pre-tax is taken as-is.
    Adding it back would report a ~90% margin for JPM."""
    h = _history(
        revenue={2023: "158", 2024: "177", 2025: "180"},
        pretax_income={2023: "61", 2024: "75", 2025: "72"},
        interest_expense={2023: "81", 2024: "90", 2025: "88"},
    )
    margins, basis = _margins(h, lender=True)
    assert basis == "pre-tax (no operating-income line filed)"
    assert all(m < Decimal("0.5") for m in margins)


def test_no_pretax_history_yields_empty_series():
    h = _history(revenue={2023: "1000"})
    assert ValuationService._ebit_series(h, False) == ([], "EBIT")
