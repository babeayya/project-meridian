"""Shared valuation types."""
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.calc.trace import CalcNode


class ValuationOutcome(BaseModel):
    model: str
    status: str = "ok"                       # ok | not_applicable
    not_applicable_reason: str | None = None
    fair_value_per_share: Decimal | None = None
    currency: str = "USD"
    low: Decimal | None = None
    high: Decimal | None = None
    confidence: float = 0.0
    outputs: dict = Field(default_factory=dict)
    trace: CalcNode | None = None
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def na(cls, model: str, reason: str, currency: str = "USD") -> "ValuationOutcome":
        return cls(model=model, status="not_applicable",
                   not_applicable_reason=reason, currency=currency)

    def caveat(self, reason: str, confidence_factor: float) -> "ValuationOutcome":
        """Attach a methodological warning and discount the model's confidence.

        Used where a model still produces a defensible number but rests on an
        assumption that does not hold for this filer. The result stays in the
        football field — hiding it would silently shift the whole blend onto
        the remaining models — but it carries less weight and says why.
        """
        self.warnings.append(reason)
        self.confidence = round(self.confidence * confidence_factor, 4)
        return self


class WaccInputs(BaseModel):
    """Every field editable; provenance is attached when the service builds
    these from live macro data."""
    risk_free_rate: Decimal
    beta: Decimal
    equity_risk_premium: Decimal = Decimal("0.05")
    cost_of_debt: Decimal | None = None      # derived from statements if None
    tax_rate: Decimal = Decimal("0.21")
    market_cap: Decimal
    total_debt: Decimal = Decimal(0)
    rf_source: str = "assumption"
    beta_source: str = "computed"


class AssumptionSet(BaseModel):
    """Editable driver assumptions for the forecast. `derivation` explains how
    each default was computed from history."""
    forecast_years: int = 5
    revenue_growth: list[Decimal]            # per forecast year
    ebit_margin: list[Decimal]               # per forecast year
    tax_rate: Decimal
    da_pct_revenue: Decimal
    capex_pct_revenue: Decimal
    capex_fade_to_da: bool = True            # capex % fades to D&A % by year N
                                             # (steady-state reinvestment)
    nwc_pct_revenue_delta: Decimal           # ΔNWC = pct × Δrevenue
    terminal_growth: Decimal = Decimal("0.025")
    exit_ev_ebitda: Decimal | None = None
    shares_diluted: Decimal
    net_debt: Decimal
    minority_interest: Decimal = Decimal(0)
    wacc: WaccInputs
    derivation: dict[str, str] = Field(default_factory=dict)
