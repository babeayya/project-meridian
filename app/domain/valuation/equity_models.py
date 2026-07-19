"""Equity-side models: DDM, Residual Income, EVA."""
from decimal import Decimal

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements import derived
from app.domain.statements.history import FinancialHistory
from app.domain.valuation import wacc as wacc_mod
from app.domain.valuation.base import AssumptionSet, ValuationOutcome

ONE = Decimal(1)
Q2 = Decimal("0.01")


def ddm(history: FinancialHistory, a: AssumptionSet,
        price: Decimal | None) -> ValuationOutcome:
    """Two-stage dividend discount model on per-share dividends."""
    model = "ddm"
    currency = history.currency
    dps_series = []
    for p in history.annual:
        div, sh = p.get("dividends_paid"), p.get("shares_diluted")
        if div and sh and div > 0 and sh > 0:
            dps_series.append((p.fiscal_year, div / sh))
    if len(dps_series) < 3:
        return ValuationOutcome.na(
            model, "requires ≥3 years of dividend history — company pays no or "
                   "too-recent dividends", currency)

    d0 = dps_series[-1][1]
    first, last = dps_series[0][1], dps_series[-1][1]
    n = dps_series[-1][0] - dps_series[0][0]
    if first <= 0 or n <= 0:
        return ValuationOutcome.na(model, "dividend history unusable", currency)
    hist_g = Decimal(str(round((float(last) / float(first)) ** (1 / n) - 1, 6)))
    g1 = min(max(hist_g, Decimal("-0.05")), Decimal("0.15"))

    ke_node = wacc_mod.cost_of_equity(a.wacc)
    ke = ke_node.result
    g_term = min(a.terminal_growth, ke - Decimal("0.01"))
    if ke <= g_term:
        return ValuationOutcome.na(model, "Ke ≤ terminal growth", currency)

    stage_years = 5
    pv = Decimal(0)
    d = d0
    for t in range(1, stage_years + 1):
        # fade growth linearly from g1 to terminal
        g_t = g1 + (g_term - g1) * Decimal(t - 1) / Decimal(stage_years - 1)
        d = d * (ONE + g_t)
        pv += d * (ONE + ke) ** -t
    tv = d * (ONE + g_term) / (ke - g_term) * (ONE + ke) ** -stage_years
    value = (pv + tv).quantize(Q2)

    node = CalcNode(
        key="ddm", label="Dividend Discount Model (two-stage, fading growth)",
        formula="V = Σ PV(DPS_t, Ke) + PV(DPS_N(1+g)/(Ke−g))",
        inputs=[CalcInput(name="dps_current", symbol="D0", value=d0.quantize(Q2)),
                CalcInput(name="stage1_growth", symbol="g1", value=g1, unit="%"),
                CalcInput(name="terminal_growth", symbol="g", value=g_term, unit="%"),
                CalcInput(name="cost_of_equity", symbol="Ke", value=ke, unit="%")],
        intermediates=[ke_node],
        result=value, unit=f"{currency}/share",
        explanation=f"Stage-1 growth {g1:.1%} from {len(dps_series)}y dividend "
                    f"history (clamped to [−5%, 15%]), fading to {g_term:.1%}.",
        method_confidence=0.8,
    )
    return ValuationOutcome(model=model, fair_value_per_share=value,
                            currency=currency, confidence=node.confidence,
                            outputs={"dps_history": [(y, str(v.quantize(Q2)))
                                                     for y, v in dps_series],
                                     "stage1_growth": str(g1)},
                            trace=node)


def residual_income(history: FinancialHistory, a: AssumptionSet,
                    price: Decimal | None) -> ValuationOutcome:
    """RI model: V = BV0 + Σ PV[(ROE_t − Ke) × BV_{t−1}], ROE fading to Ke."""
    model = "residual_income"
    currency = history.currency
    p = history.latest
    if p is None:
        return ValuationOutcome.na(model, "no fundamentals ingested", currency)
    vals = p.require("total_equity", "net_income")
    if vals is None or a.shares_diluted <= 0:
        return ValuationOutcome.na(model, "book equity / net income unavailable", currency)
    equity, ni = vals
    if equity <= 0:
        return ValuationOutcome.na(model, "negative book equity", currency)

    ke_node = wacc_mod.cost_of_equity(a.wacc)
    ke = ke_node.result
    roe0 = ni / equity
    horizon = 10
    bv = equity
    pv_ri = Decimal(0)
    payout = Decimal("0.35")
    div = p.get("dividends_paid")
    if div and ni > 0:
        payout = min(max(div / ni, Decimal(0)), Decimal("0.9"))
    for t in range(1, horizon + 1):
        roe_t = roe0 + (ke - roe0) * Decimal(t) / Decimal(horizon)  # fade to Ke
        earnings = bv * roe_t
        ri = (roe_t - ke) * bv
        pv_ri += ri * (ONE + ke) ** -t
        bv = bv + earnings * (ONE - payout)  # clean surplus
    value_total = equity + pv_ri
    per_share = (value_total / a.shares_diluted).quantize(Q2)

    node = CalcNode(
        key="residual_income", label="Residual Income Model",
        formula="V = BV0 + Σ PV[(ROE_t − Ke) × BV_{t−1}]",
        inputs=[CalcInput(name="book_value", symbol="BV0", value=equity.quantize(Q2)),
                CalcInput(name="current_roe", symbol="ROE0",
                          value=roe0.quantize(Decimal("0.0001")), unit="%"),
                CalcInput(name="cost_of_equity", symbol="Ke", value=ke, unit="%"),
                CalcInput(name="payout_ratio", symbol="payout", value=payout, unit="%")],
        intermediates=[ke_node],
        result=per_share, unit=f"{currency}/share",
        explanation=f"ROE fades linearly from {roe0:.1%} to Ke over {horizon} years "
                    "(competitive convergence); clean-surplus book value walk.",
        method_confidence=0.8,
    )
    return ValuationOutcome(model=model, fair_value_per_share=per_share,
                            currency=currency, confidence=node.confidence,
                            outputs={"bv0": str(equity.quantize(Q2)),
                                     "pv_residual_income": str(pv_ri.quantize(Q2)),
                                     "roe0": str(roe0.quantize(Decimal('0.0001')))},
                            trace=node)


def eva(history: FinancialHistory, a: AssumptionSet,
        price: Decimal | None) -> ValuationOutcome:
    """EVA valuation: V_firm = IC0 + Σ PV(EVA_t), EVA = NOPAT − WACC×IC."""
    model = "eva"
    currency = history.currency
    p = history.latest
    if p is None:
        return ValuationOutcome.na(model, "no fundamentals ingested", currency)
    ic_node = derived.invested_capital(p)
    nopat_node = derived.nopat(p)
    if ic_node is None or nopat_node is None or ic_node.result <= 0:
        return ValuationOutcome.na(model, "invested capital / NOPAT unavailable", currency)

    wacc_node = wacc_mod.wacc(a.wacc)
    r = wacc_node.result
    roic0 = nopat_node.result / ic_node.result
    horizon = 10
    ic = ic_node.result
    pv_eva = Decimal(0)
    reinvest = Decimal("0.4")
    for t in range(1, horizon + 1):
        roic_t = roic0 + (r - roic0) * Decimal(t) / Decimal(horizon)  # fade to WACC
        nopat_t = ic * roic_t
        eva_t = (roic_t - r) * ic
        pv_eva += eva_t * (ONE + r) ** -t
        ic = ic + nopat_t * reinvest
    firm_value = ic_node.result + pv_eva
    equity_value = firm_value - a.net_debt - a.minority_interest
    per_share = (equity_value / a.shares_diluted).quantize(Q2)

    node = CalcNode(
        key="eva", label="Economic Value Added",
        formula="V = IC0 + Σ PV[(ROIC_t − WACC) × IC_{t−1}] − Net Debt",
        inputs=[CalcInput(name="invested_capital", symbol="IC0",
                          value=ic_node.result.quantize(Q2)),
                CalcInput(name="current_roic", symbol="ROIC0",
                          value=roic0.quantize(Decimal("0.0001")), unit="%"),
                CalcInput(name="wacc", symbol="WACC", value=r, unit="%")],
        intermediates=[wacc_node, ic_node, nopat_node],
        result=per_share, unit=f"{currency}/share",
        explanation=f"ROIC fades from {roic0:.1%} to WACC over {horizon}y "
                    "(economic profits competed away); 40% NOPAT reinvestment.",
        method_confidence=0.75,
    )
    return ValuationOutcome(model=model, fair_value_per_share=per_share,
                            currency=currency, confidence=node.confidence,
                            outputs={"ic0": str(ic_node.result.quantize(Q2)),
                                     "pv_eva": str(pv_eva.quantize(Q2)),
                                     "roic0": str(roic0.quantize(Decimal('0.0001')))},
                            trace=node)


def asset_based(history: FinancialHistory, a: AssumptionSet,
                price: Decimal | None) -> ValuationOutcome:
    """Book-value floor: tangible book per share."""
    model = "asset_based"
    currency = history.currency
    p = history.latest
    if p is None:
        return ValuationOutcome.na(model, "no fundamentals ingested", currency)
    equity = p.get("total_equity")
    if equity is None or a.shares_diluted <= 0:
        return ValuationOutcome.na(model, "book equity unavailable", currency)
    goodwill = p.get("goodwill") or Decimal(0)
    intangibles = p.get("intangibles") or Decimal(0)
    tangible = equity - goodwill - intangibles
    per_share = (tangible / a.shares_diluted).quantize(Q2)
    node = CalcNode(
        key="asset_based", label="Asset-Based (Tangible Book Value)",
        formula="TBV/share = (Equity − Goodwill − Intangibles) / Diluted Shares",
        inputs=[CalcInput(name="total_equity", symbol="Equity", value=equity),
                CalcInput(name="goodwill", symbol="Goodwill", value=goodwill),
                CalcInput(name="intangibles", symbol="Intangibles", value=intangibles),
                CalcInput(name="shares_diluted", symbol="Shares", value=a.shares_diluted)],
        result=per_share, unit=f"{currency}/share",
        explanation="Liquidation-style floor; ignores going-concern value. Most "
                    "meaningful for asset-heavy or deep-value situations.",
        method_confidence=0.7,
    )
    return ValuationOutcome(model=model, fair_value_per_share=per_share,
                            currency=currency, confidence=node.confidence,
                            outputs={"tangible_book": str(tangible.quantize(Q2))},
                            trace=node)
