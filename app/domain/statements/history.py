"""Value objects the financial engine computes from. Pure data, no I/O."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class PeriodFinancials(BaseModel):
    fiscal_year: int
    period_end: date
    period_type: str = "annual"           # 'annual' | 'quarterly'
    currency: str = "USD"
    source: str = ""
    items: dict[str, Decimal] = Field(default_factory=dict)

    def get(self, key: str) -> Decimal | None:
        return self.items.get(key)

    def require(self, *keys: str) -> list[Decimal] | None:
        """All-or-nothing fetch; None if any key is missing (caller reports
        'insufficient data' rather than computing garbage)."""
        vals = [self.items.get(k) for k in keys]
        return None if any(v is None for v in vals) else vals  # type: ignore[return-value]

    @property
    def total_debt(self) -> Decimal | None:
        st, lt = self.items.get("short_term_debt"), self.items.get("long_term_debt")
        if st is None and lt is None:
            return None
        return (st or Decimal(0)) + (lt or Decimal(0))


class FinancialHistory(BaseModel):
    company_name: str = ""
    currency: str = "USD"
    annual: list[PeriodFinancials] = Field(default_factory=list)     # ascending FY
    quarterly: list[PeriodFinancials] = Field(default_factory=list)  # ascending

    @property
    def latest(self) -> PeriodFinancials | None:
        return self.annual[-1] if self.annual else None

    @property
    def prior(self) -> PeriodFinancials | None:
        return self.annual[-2] if len(self.annual) >= 2 else None

    def year(self, fiscal_year: int) -> PeriodFinancials | None:
        for p in self.annual:
            if p.fiscal_year == fiscal_year:
                return p
        return None

    def latest_value(self, key: str) -> Decimal | None:
        """Most recent non-null value — newest filings often lag on some
        line items (e.g. diluted shares right after fiscal year end)."""
        for p in reversed(self.annual):
            v = p.items.get(key)
            if v is not None:
                return v
        return None

    def series(self, key: str) -> list[tuple[int, Decimal]]:
        return [
            (p.fiscal_year, v) for p in self.annual
            if (v := p.items.get(key)) is not None
        ]

    def cagr(self, key: str, years: int) -> Decimal | None:
        """Compound annual growth over up to `years` most recent yearly steps."""
        pts = self.series(key)
        if len(pts) < 2:
            return None
        window = pts[-(years + 1):]
        first, last = window[0][1], window[-1][1]
        n = window[-1][0] - window[0][0]
        if first <= 0 or last <= 0 or n <= 0:
            return None
        growth = (float(last) / float(first)) ** (1.0 / n) - 1.0
        return Decimal(str(round(growth, 6)))

    def average(self, key: str, years: int) -> Decimal | None:
        pts = [v for _, v in self.series(key)[-years:]]
        if not pts:
            return None
        return sum(pts) / len(pts)
