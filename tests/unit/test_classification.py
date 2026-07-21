"""Structural detection of financial filers.

Sector/industry are never persisted by the resolution path, so hint-matching
alone evaluated False for every company in the database. These cover the
structural test that backs it.
"""
from datetime import date
from decimal import Decimal

from app.domain.statements.classification import (
    is_financial,
    looks_like_lender,
    sector_hints_financial,
    sector_hints_manufacturer,
)
from app.domain.statements.history import FinancialHistory, PeriodFinancials


def _history(**series: dict[int, str]) -> FinancialHistory:
    years = sorted({fy for s in series.values() for fy in s})
    return FinancialHistory(currency="USD", annual=[
        PeriodFinancials(
            fiscal_year=fy, period_end=date(fy, 12, 31), currency="USD",
            items={k: Decimal(s[fy]) for k, s in series.items() if fy in s},
        )
        for fy in years
    ])


BANK = _history(   # JPM-shaped: interest ~50% of revenue
    revenue={2023: "158", 2024: "177", 2025: "180"},
    interest_expense={2023: "81", 2024: "90", 2025: "88"},
)
INDUSTRIAL = _history(   # CAT-shaped: interest a few percent of revenue
    revenue={2023: "1000", 2024: "1100", 2025: "1200"},
    interest_expense={2023: "30", 2024: "33", 2025: "36"},
)


def test_lender_detected_from_structure_with_no_metadata():
    assert looks_like_lender(BANK) is True
    assert is_financial(BANK, sector=None, industry=None) is True


def test_operating_company_not_flagged():
    assert looks_like_lender(INDUSTRIAL) is False
    assert is_financial(INDUSTRIAL, sector=None, industry=None) is False


def test_sector_metadata_alone_is_sufficient():
    """When a provider does populate sector, trust it even if the structural
    signal is absent — an insurer carries little interest expense."""
    insurer = _history(revenue={2025: "1000"}, interest_expense={2025: "10"})
    assert looks_like_lender(insurer) is False
    assert is_financial(insurer, "Financial Services", "Insurance—Life") is True


def test_absent_metadata_does_not_veto_the_structural_signal():
    assert is_financial(BANK, "", "") is True


def test_no_interest_history_is_not_a_lender():
    assert looks_like_lender(_history(revenue={2025: "1000"})) is False


def test_zero_revenue_year_does_not_divide_by_zero():
    h = _history(revenue={2025: "0"}, interest_expense={2025: "50"})
    assert looks_like_lender(h) is False


def test_only_recent_years_are_considered():
    """A distressed year long ago should not permanently brand a filer."""
    h = _history(
        revenue={2019: "100", 2022: "1000", 2023: "1100", 2024: "1200"},
        interest_expense={2019: "60", 2022: "20", 2023: "22", 2024: "24"},
    )
    assert looks_like_lender(h) is False


def test_sector_hint_helpers():
    assert sector_hints_financial("Financial Services", None) is True
    assert sector_hints_financial(None, None) is False
    assert sector_hints_manufacturer(None, "Aerospace & Defense") is True
    assert sector_hints_manufacturer(None, None) is False
