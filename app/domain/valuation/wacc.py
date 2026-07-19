"""Weighted average cost of capital with a full audit trace."""
from decimal import Decimal

from app.domain.calc.trace import CalcInput, CalcNode, Provenance
from app.domain.valuation.base import WaccInputs

ONE = Decimal(1)
Q4 = Decimal("0.0001")


def cost_of_equity(w: WaccInputs) -> CalcNode:
    ke = w.risk_free_rate + w.beta * w.equity_risk_premium
    return CalcNode(
        key="wacc.cost_of_equity", label="Cost of Equity (CAPM)",
        formula="Ke = Rf + β × ERP",
        inputs=[
            CalcInput(name="risk_free_rate", symbol="Rf", value=w.risk_free_rate,
                      unit="%", source=Provenance(provider=w.rf_source), confidence=0.95),
            CalcInput(name="levered_beta", symbol="β", value=w.beta,
                      source=Provenance(provider=w.beta_source), confidence=0.85),
            CalcInput(name="equity_risk_premium", symbol="ERP",
                      value=w.equity_risk_premium, unit="%",
                      source=Provenance(provider="assumption", editable=True),
                      confidence=0.80),
        ],
        result=ke.quantize(Q4), unit="%",
        explanation="CAPM: required equity return given systematic risk.",
    )


def wacc(w: WaccInputs) -> CalcNode:
    ke_node = cost_of_equity(w)
    kd = w.cost_of_debt if w.cost_of_debt is not None else w.risk_free_rate + Decimal("0.015")
    kd_assumed = w.cost_of_debt is None
    mcap_missing = w.market_cap <= 0
    if mcap_missing:
        # without a market cap the market-value weights are meaningless;
        # discount at Ke (conservative) and say so in the trace
        we = ONE
    else:
        total_cap = w.market_cap + w.total_debt
        we = w.market_cap / total_cap if total_cap else ONE
    wd = ONE - we
    result = we * ke_node.result + wd * kd * (ONE - w.tax_rate)
    node = CalcNode(
        key="wacc", label="Weighted Average Cost of Capital",
        formula="WACC = wE × Ke + wD × Kd × (1 − t)",
        inputs=[
            CalcInput(name="equity_weight", symbol="wE", value=we.quantize(Q4)),
            CalcInput(name="cost_of_equity", symbol="Ke", value=ke_node.result, unit="%"),
            CalcInput(name="debt_weight", symbol="wD", value=wd.quantize(Q4)),
            CalcInput(name="cost_of_debt", symbol="Kd", value=kd.quantize(Q4), unit="%",
                      confidence=0.7 if kd_assumed else 0.9),
            CalcInput(name="tax_rate", symbol="t", value=w.tax_rate, unit="%"),
        ],
        intermediates=[ke_node],
        result=result.quantize(Q4), unit="%",
        explanation="Market-value weights; cost of debt "
                    + ("estimated as Rf + 150bp (no interest/debt data)."
                       if kd_assumed else "from interest expense / average debt."),
    )
    if kd_assumed:
        node.assumptions.append("cost of debt assumed = Rf + 150bp")
    if mcap_missing:
        node.assumptions.append(
            "market cap unavailable — equity-only weighting (WACC = Ke)")
    return node
