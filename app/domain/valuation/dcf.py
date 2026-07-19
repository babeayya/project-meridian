"""Driver-based DCF: FCFF (enterprise) and FCFE (equity) variants.

Forecast model: revenue path × margin path → NOPAT; D&A/CapEx/ΔNWC as revenue
drivers; terminal value by Gordon growth with an exit-multiple cross-check.
Every year and every bridge step is a CalcNode in the returned trace.
"""
from decimal import Decimal

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements.history import FinancialHistory
from app.domain.valuation import wacc as wacc_mod
from app.domain.valuation.base import AssumptionSet, ValuationOutcome

ONE = Decimal(1)
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


def _forecast_fcff(history: FinancialHistory,
                   a: AssumptionSet) -> tuple[list[dict], list[CalcNode]]:
    base_rev = history.latest.get("revenue") if history.latest else None
    if base_rev is None:
        raise ValueError("revenue history required")
    years: list[dict] = []
    nodes: list[CalcNode] = []
    rev_prev = base_rev
    n = a.forecast_years
    for i in range(n):
        g = a.revenue_growth[min(i, len(a.revenue_growth) - 1)]
        margin = a.ebit_margin[min(i, len(a.ebit_margin) - 1)]
        rev = rev_prev * (ONE + g)
        ebit = rev * margin
        nopat = ebit * (ONE - a.tax_rate)
        da = rev * a.da_pct_revenue
        capex_pct = a.capex_pct_revenue
        if a.capex_fade_to_da and n > 1:
            # steady-state reinvestment: capex % converges to D&A % by year N
            capex_pct = (a.capex_pct_revenue
                         + (a.da_pct_revenue - a.capex_pct_revenue)
                         * Decimal(i) / Decimal(n - 1))
        capex = rev * capex_pct
        dnwc = (rev - rev_prev) * a.nwc_pct_revenue_delta
        fcff = nopat + da - capex - dnwc
        years.append({"year": i + 1, "revenue": rev, "ebit": ebit, "nopat": nopat,
                      "da": da, "capex": capex, "dnwc": dnwc, "fcff": fcff,
                      "growth": g, "margin": margin})
        nodes.append(CalcNode(
            key=f"dcf.year{i+1}.fcff", label=f"Year {i+1} FCFF",
            formula="FCFF = Rev×margin×(1−t) + D&A − CapEx − ΔNWC",
            inputs=[
                CalcInput(name="revenue", symbol="Rev", value=rev.quantize(Q2)),
                CalcInput(name="ebit_margin", symbol="margin", value=margin, unit="%"),
                CalcInput(name="tax_rate", symbol="t", value=a.tax_rate, unit="%"),
                CalcInput(name="da", symbol="D&A", value=da.quantize(Q2)),
                CalcInput(name="capex", symbol="CapEx", value=capex.quantize(Q2)),
                CalcInput(name="dnwc", symbol="ΔNWC", value=dnwc.quantize(Q2)),
            ],
            result=fcff.quantize(Q2), unit=history.currency,
        ))
        rev_prev = rev
    return years, nodes


def dcf_fcff(history: FinancialHistory, a: AssumptionSet,
             price: Decimal | None) -> ValuationOutcome:
    model = "dcf_fcff"
    currency = history.currency
    if history.latest is None or history.latest.get("revenue") is None:
        return ValuationOutcome.na(model, "no revenue history ingested", currency)

    wacc_node = wacc_mod.wacc(a.wacc)
    r = wacc_node.result
    if r <= a.terminal_growth:
        return ValuationOutcome.na(
            model, f"WACC {r:.2%} ≤ terminal growth {a.terminal_growth:.2%} — "
                   "Gordon terminal value undefined; lower g or revisit WACC inputs.",
            currency)

    years, year_nodes = _forecast_fcff(history, a)
    pv_explicit = Decimal(0)
    for y in years:
        y["discount_factor"] = (ONE + r) ** -y["year"]
        y["pv"] = y["fcff"] * y["discount_factor"]
        pv_explicit += y["pv"]

    fcff_n = years[-1]["fcff"]
    if fcff_n <= 0:
        return ValuationOutcome.na(
            model, "terminal-year FCFF is negative — reinvestment (capex + NWC) "
                   "exceeds after-tax operating profit on these drivers, so a "
                   "going-concern DCF is not meaningful. Adjust the capex/margin "
                   "assumptions or rely on multiples / residual-income models.",
            currency)
    tv_gordon = fcff_n * (ONE + a.terminal_growth) / (r - a.terminal_growth)
    pv_tv = tv_gordon * (ONE + r) ** -a.forecast_years
    tv_node = CalcNode(
        key="dcf.terminal", label="Terminal Value (Gordon Growth)",
        formula="TV = FCFF_N × (1 + g) / (WACC − g)",
        inputs=[CalcInput(name="fcff_final", symbol="FCFF_N", value=fcff_n.quantize(Q2)),
                CalcInput(name="terminal_growth", symbol="g", value=a.terminal_growth, unit="%"),
                CalcInput(name="wacc", symbol="WACC", value=r, unit="%")],
        result=tv_gordon.quantize(Q2), unit=currency,
    )

    exit_check = None
    if a.exit_ev_ebitda is not None:
        ebitda_n = years[-1]["ebit"] + years[-1]["da"]
        exit_check = (ebitda_n * a.exit_ev_ebitda * (ONE + r) ** -a.forecast_years)

    ev = pv_explicit + pv_tv
    equity_value = ev - a.net_debt - a.minority_interest
    if a.shares_diluted <= 0:
        return ValuationOutcome.na(model, "diluted share count unavailable", currency)
    per_share = (equity_value / a.shares_diluted).quantize(Q2)

    bridge = CalcNode(
        key="dcf.fcff", label="DCF (FCFF → equity value per share)",
        formula="Value = (Σ PV(FCFF) + PV(TV) − Net Debt − Minorities) / Diluted Shares",
        inputs=[
            CalcInput(name="pv_explicit", symbol="Σ PV(FCFF)", value=pv_explicit.quantize(Q2)),
            CalcInput(name="pv_terminal", symbol="PV(TV)", value=pv_tv.quantize(Q2)),
            CalcInput(name="net_debt", symbol="Net Debt", value=a.net_debt.quantize(Q2)),
            CalcInput(name="minority_interest", symbol="Minorities", value=a.minority_interest),
            CalcInput(name="shares_diluted", symbol="Diluted Shares", value=a.shares_diluted),
        ],
        intermediates=[wacc_node, *year_nodes, tv_node],
        result=per_share, unit=f"{currency}/share",
        explanation="Enterprise DCF: unlevered cash flows discounted at WACC, "
                    "bridged to equity via net debt.",
        method_confidence=0.9,
    )

    terminal_share = float(pv_tv / ev) if ev else 1.0
    # value range: ±50bp WACC and ±25bp terminal growth corner cases
    lo, hi = _dcf_range(years, a, r)
    outputs = {
        "wacc": str(r), "ev": str(ev.quantize(Q2)),
        "net_debt": str(a.net_debt.quantize(Q2)),
        "equity_value": str(equity_value.quantize(Q2)),
        "pv_explicit": str(pv_explicit.quantize(Q2)),
        "pv_terminal": str(pv_tv.quantize(Q2)),
        "terminal_share_of_ev": round(terminal_share, 4),
        "terminal_value_gordon": str(tv_gordon.quantize(Q2)),
        "terminal_value_exit_multiple_pv": str(exit_check.quantize(Q2)) if exit_check else None,
        "forecast": [{k: str(v.quantize(Q4)) if isinstance(v, Decimal) else v
                      for k, v in y.items()} for y in years],
    }
    confidence = round(bridge.confidence * (1.0 - min(terminal_share, 0.85) * 0.3), 4)
    return ValuationOutcome(
        model=model, fair_value_per_share=per_share, currency=currency,
        low=lo, high=hi, confidence=confidence, outputs=outputs, trace=bridge,
    )


def _dcf_range(years: list[dict], a: AssumptionSet, r: Decimal) -> tuple[Decimal, Decimal]:
    values = []
    for dr in (Decimal("-0.005"), Decimal(0), Decimal("0.005")):
        for dg in (Decimal("-0.0025"), Decimal(0), Decimal("0.0025")):
            rr, gg = r + dr, a.terminal_growth + dg
            if rr <= gg:
                continue
            pv = sum(y["fcff"] * (ONE + rr) ** -y["year"] for y in years)
            tv = years[-1]["fcff"] * (ONE + gg) / (rr - gg) * (ONE + rr) ** -a.forecast_years
            eq = pv + tv - a.net_debt - a.minority_interest
            values.append(eq / a.shares_diluted)
    return (min(values).quantize(Q2), max(values).quantize(Q2)) if values \
        else (Decimal(0), Decimal(0))


def dcf_fcfe(history: FinancialHistory, a: AssumptionSet,
             price: Decimal | None) -> ValuationOutcome:
    """Equity DCF: FCFE ≈ FCFF − after-tax interest, discounted at Ke."""
    model = "dcf_fcfe"
    currency = history.currency
    p = history.latest
    if p is None or p.get("revenue") is None:
        return ValuationOutcome.na(model, "no revenue history ingested", currency)

    ke_node = wacc_mod.cost_of_equity(a.wacc)
    ke = ke_node.result
    if ke <= a.terminal_growth:
        return ValuationOutcome.na(
            model, f"Ke {ke:.2%} ≤ terminal growth — terminal value undefined", currency)

    interest = p.get("interest_expense") or Decimal(0)
    after_tax_interest = interest * (ONE - a.tax_rate)
    years, _ = _forecast_fcff(history, a)
    pv = Decimal(0)
    fcfe_years = []
    for y in years:
        fcfe = y["fcff"] - after_tax_interest
        pv += fcfe * (ONE + ke) ** -y["year"]
        fcfe_years.append({"year": y["year"], "fcfe": str(fcfe.quantize(Q2))})
    fcfe_n = years[-1]["fcff"] - after_tax_interest
    tv = fcfe_n * (ONE + a.terminal_growth) / (ke - a.terminal_growth)
    equity_value = pv + tv * (ONE + ke) ** -a.forecast_years
    per_share = (equity_value / a.shares_diluted).quantize(Q2)

    node = CalcNode(
        key="dcf.fcfe", label="DCF (FCFE)",
        formula="Value = Σ PV(FCFE, Ke) + PV(TV) ; FCFE = FCFF − Interest×(1−t)",
        inputs=[CalcInput(name="cost_of_equity", symbol="Ke", value=ke, unit="%"),
                CalcInput(name="after_tax_interest", symbol="Int(1−t)",
                          value=after_tax_interest.quantize(Q2)),
                CalcInput(name="shares_diluted", symbol="Shares", value=a.shares_diluted)],
        intermediates=[ke_node],
        result=per_share, unit=f"{currency}/share",
        assumptions=["net borrowing assumed 0 (constant debt)"],
        method_confidence=0.85,
    )
    return ValuationOutcome(
        model=model, fair_value_per_share=per_share, currency=currency,
        confidence=node.confidence,
        outputs={"ke": str(ke), "equity_value": str(equity_value.quantize(Q2)),
                 "fcfe_forecast": fcfe_years},
        trace=node,
    )
