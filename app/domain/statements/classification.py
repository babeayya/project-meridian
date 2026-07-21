"""Filer classification. Pure functions over reported history.

Sector/industry metadata is the obvious way to spot a bank, but it is not
reliable here: the resolution path persists neither field, so `sector` is NULL
for every company in the database and any hint-matching on it silently
evaluates False. Classification therefore reads the financials themselves and
treats the metadata as a corroborating hint when it happens to be present.
"""
from decimal import Decimal

from app.domain.statements.history import FinancialHistory

FINANCIAL_SECTOR_HINTS = ("bank", "insurance", "financial", "capital markets")
MANUFACTURER_HINTS = ("manufactur", "industrial", "auto", "aerospace",
                      "machinery", "chemicals", "materials", "hardware")

# Interest as a share of revenue. Lenders fund assets with deposits and debt,
# so interest is a cost of revenue and runs to tens of percent (JPM ~50%).
# An operating company carrying this much interest expense year after year
# would be in distress, not steady state.
LENDER_INTEREST_RATIO = Decimal("0.15")
LOOKBACK_YEARS = 3


def sector_hints_financial(sector: str | None, industry: str | None) -> bool:
    """True when metadata explicitly says financial. Absence proves nothing."""
    text = f"{sector or ''} {industry or ''}".lower()
    return any(h in text for h in FINANCIAL_SECTOR_HINTS)


def sector_hints_manufacturer(sector: str | None, industry: str | None) -> bool:
    text = f"{sector or ''} {industry or ''}".lower()
    return any(h in text for h in MANUFACTURER_HINTS)


def looks_like_lender(history: FinancialHistory) -> bool:
    """Structural test: interest expense is a material share of revenue in any
    of the recent years reported."""
    revenue = dict(history.series("revenue"))
    interest = history.series("interest_expense")[-LOOKBACK_YEARS:]
    return any(
        revenue.get(fy) and revenue[fy] > 0
        and value / revenue[fy] > LENDER_INTEREST_RATIO
        for fy, value in interest
    )


def is_financial(history: FinancialHistory, sector: str | None = None,
                 industry: str | None = None) -> bool:
    """Whether enterprise-value frameworks break down for this filer.

    Either signal is sufficient: metadata when present, structure otherwise.
    """
    return sector_hints_financial(sector, industry) or looks_like_lender(history)
