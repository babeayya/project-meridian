"""Reverse DCF, sensitivity grid, scenario weighting, Monte Carlo DCF,
expected return decomposition, and the summary/football-field aggregator."""
import random
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.calc.trace import CalcInput, CalcNode
from app.domain.statements.history import FinancialHistory
from app.domain.valuation import wacc as wacc_mod
from app.domain.valuation.base import AssumptionSet, ValuationOutcome
from app.domain.valuation.dcf import dcf_fcff

ONE = Decimal(1)
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


def _dcf_value_float(base_rev: float, years: int, growth: float, margin: float,
                     tax: float, da_pct: float, capex_pct: float, nwc_pct: float,
                     r: float, g_term: float, net_debt: float, shares: float,
                     capex_fade: bool = True) -> float | None:
    """Float-math DCF core for iterative methods (reverse DCF, Monte Carlo).
    Mirrors dcf.py including the capex→D&A terminal-year fade."""
    if r <= g_term or shares <= 0:
        return None
    rev_prev, pv = base_rev, 0.0
    fcff = 0.0
    for t in range(1, years + 1):
        rev = rev_prev * (1 + growth)
        cx = capex_pct
        if capex_fade and years > 1:
            cx = capex_pct + (da_pct - capex_pct) * (t - 1) / (years - 1)
        fcff = (rev * margin * (1 - tax) + rev * da_pct - rev * cx
                - (rev - rev_prev) * nwc_pct)
        pv += fcff / (1 + r) ** t
        rev_prev = rev
    if fcff <= 0:
        return None
    tv = fcff * (1 + g_term) / (r - g_term) / (1 + r) ** years
    return (pv + tv - net_debt) / shares


def _float_params(history: FinancialHistory, a: AssumptionSet) -> dict | None:
    base_rev = history.latest.get("revenue") if history.latest else None
    if base_rev is None:
        return None
    return {
        "base_rev": float(base_rev), "years": a.forecast_years,
        "growth": float(sum(a.revenue_growth) / len(a.revenue_growth)),
        "margin": float(sum(a.ebit_margin) / len(a.ebit_margin)),
        "tax": float(a.tax_rate), "da_pct": float(a.da_pct_revenue),
        "capex_pct": float(a.capex_pct_revenue), "nwc_pct": float(a.nwc_pct_revenue_delta),
        "g_term": float(a.terminal_growth), "net_debt": float(a.net_debt),
        "shares": float(a.shares_diluted), "capex_fade": a.capex_fade_to_da,
    }


def reverse_dcf(history: FinancialHistory, a: AssumptionSet,
                price: Decimal | None) -> ValuationOutcome:
    """Solve for the constant revenue growth the market price implies."""
    model = "reverse_dcf"
    currency = history.currency
    params = _float_params(history, a)
    if params is None or price is None or price <= 0:
        return ValuationOutcome.na(model, "needs revenue history and current price", currency)
    r = float(wacc_mod.wacc(a.wacc).result)
    target = float(price)

    def value_at(g: float) -> float | None:
        p = dict(params)
        p["growth"] = g
        return _dcf_value_float(r=r, **p)

    lo_g, hi_g = -0.20, 0.60
    v_lo, v_hi = value_at(lo_g), value_at(hi_g)
    if v_lo is None or v_hi is None or not (v_lo <= target <= v_hi):
        return ValuationOutcome.na(
            model, f"price {price} outside solvable growth range "
                   f"[{lo_g:.0%}, {hi_g:.0%}] given current margins/WACC", currency)
    for _ in range(60):  # bisection
        mid = (lo_g + hi_g) / 2
        v = value_at(mid)
        if v is None:
            break
        if v < target:
            lo_g = mid
        else:
            hi_g = mid
    implied_g = (lo_g + hi_g) / 2

    hist_g = history.cagr("revenue", 5)
    verdict = "n/a"
    if hist_g is not None:
        gap = implied_g - float(hist_g)
        verdict = ("market expects LESS growth than history — potential value"
                   if gap < -0.02 else
                   "market expects MORE growth than history — priced for acceleration"
                   if gap > 0.02 else "market expectations in line with history")
    node = CalcNode(
        key="reverse_dcf", label="Reverse DCF (implied growth)",
        formula="solve g such that DCF(g) = market price",
        inputs=[CalcInput(name="price", symbol="Price", value=price),
                CalcInput(name="wacc", symbol="WACC", value=Decimal(str(round(r, 4))), unit="%")],
        result=Decimal(str(round(implied_g, 4))), unit="%",
        explanation=f"The market price implies {implied_g:.1%} annual revenue growth "
                    f"for {a.forecast_years} years at current margins. "
                    f"Historical 5y CAGR: "
                    f"{float(hist_g):.1%}. " if hist_g is not None else "",
        method_confidence=0.85,
    )
    return ValuationOutcome(
        model=model, fair_value_per_share=None, currency=currency,
        confidence=node.confidence,
        outputs={"implied_growth": round(implied_g, 4),
                 "historical_5y_cagr": float(hist_g) if hist_g is not None else None,
                 "verdict": verdict},
        trace=node,
    )


class SensitivityResult(BaseModel):
    x_var: str
    y_var: str
    x_values: list[str]
    y_values: list[str]
    matrix: list[list[str | None]]     # fair values, rows = y, cols = x


def sensitivity(history: FinancialHistory, a: AssumptionSet,
                steps: int = 5) -> SensitivityResult | None:
    """WACC × terminal-growth grid of DCF fair values."""
    params = _float_params(history, a)
    if params is None:
        return None
    r0 = float(wacc_mod.wacc(a.wacc).result)
    g0 = float(a.terminal_growth)
    half = steps // 2
    xs = [round(r0 + 0.005 * (i - half), 4) for i in range(steps)]
    ys = [round(g0 + 0.0025 * (i - half), 4) for i in range(steps)]
    matrix: list[list[str | None]] = []
    for g in ys:
        row: list[str | None] = []
        for r in xs:
            p = dict(params)
            p["g_term"] = g
            v = _dcf_value_float(r=r, **p)
            row.append(str(round(v, 2)) if v is not None else None)
        matrix.append(row)
    return SensitivityResult(
        x_var="wacc", y_var="terminal_growth",
        x_values=[f"{x:.2%}" for x in xs], y_values=[f"{y:.2%}" for y in ys],
        matrix=matrix,
    )


class Scenario(BaseModel):
    name: str
    probability: float
    growth_delta: Decimal = Decimal(0)      # added to every forecast-year growth
    margin_delta: Decimal = Decimal(0)
    terminal_growth_delta: Decimal = Decimal(0)


DEFAULT_SCENARIOS = [
    Scenario(name="bear", probability=0.25, growth_delta=Decimal("-0.04"),
             margin_delta=Decimal("-0.03"), terminal_growth_delta=Decimal("-0.005")),
    Scenario(name="base", probability=0.50),
    Scenario(name="bull", probability=0.25, growth_delta=Decimal("0.04"),
             margin_delta=Decimal("0.02"), terminal_growth_delta=Decimal("0.005")),
]


def scenarios(history: FinancialHistory, a: AssumptionSet, price: Decimal | None,
              cases: list[Scenario] | None = None) -> ValuationOutcome:
    model = "scenario"
    currency = history.currency
    cases = cases or DEFAULT_SCENARIOS
    total_p = sum(c.probability for c in cases)
    if abs(total_p - 1.0) > 1e-6:
        return ValuationOutcome.na(model, f"scenario probabilities sum to {total_p}, not 1")

    results = []
    weighted = Decimal(0)
    for c in cases:
        adjusted = a.model_copy(deep=True)
        adjusted.revenue_growth = [g + c.growth_delta for g in a.revenue_growth]
        adjusted.ebit_margin = [max(m + c.margin_delta, Decimal("0.01"))
                                for m in a.ebit_margin]
        adjusted.terminal_growth = a.terminal_growth + c.terminal_growth_delta
        out = dcf_fcff(history, adjusted, price)
        if out.status != "ok" or out.fair_value_per_share is None:
            return ValuationOutcome.na(model, f"{c.name} case failed: "
                                              f"{out.not_applicable_reason}", currency)
        weighted += out.fair_value_per_share * Decimal(str(c.probability))
        results.append({"name": c.name, "probability": c.probability,
                        "fair_value": str(out.fair_value_per_share)})
    weighted = weighted.quantize(Q2)
    mos = None
    if price and price > 0:
        mos = float((weighted - price) / weighted) if weighted else None
    node = CalcNode(
        key="scenario", label="Probability-Weighted Scenario Valuation",
        formula="V = Σ p_i × DCF_i ; MoS = 1 − Price/V",
        inputs=[CalcInput(name=r["name"], symbol=f"p={r['probability']}",
                          value=Decimal(r["fair_value"])) for r in results],
        result=weighted, unit=f"{currency}/share",
        method_confidence=0.85,
    )
    return ValuationOutcome(
        model=model, fair_value_per_share=weighted, currency=currency,
        low=min(Decimal(r["fair_value"]) for r in results),
        high=max(Decimal(r["fair_value"]) for r in results),
        confidence=node.confidence,
        outputs={"scenarios": results, "margin_of_safety": mos},
        trace=node,
    )


class MonteCarloResult(BaseModel):
    iterations: int
    seed: int
    mean: float
    percentiles: dict[str, float]
    prob_above_price: float | None
    histogram: list[dict] = Field(default_factory=list)


def monte_carlo_dcf(history: FinancialHistory, a: AssumptionSet,
                    price: Decimal | None, iterations: int = 10_000,
                    seed: int = 42) -> ValuationOutcome:
    model = "monte_carlo_dcf"
    currency = history.currency
    params = _float_params(history, a)
    if params is None:
        return ValuationOutcome.na(model, "needs revenue history", currency)
    rng = random.Random(seed)
    r0 = float(wacc_mod.wacc(a.wacc).result)
    g_mu, m_mu = params["growth"], params["margin"]
    g_sigma = max(abs(g_mu) * 0.4, 0.02)     # dispersion scales with the estimate
    values: list[float] = []
    for _ in range(iterations):
        p = dict(params)
        p["growth"] = rng.gauss(g_mu, g_sigma)
        p["margin"] = max(rng.triangular(m_mu * 0.8, m_mu * 1.15, m_mu), 0.005)
        r = max(rng.gauss(r0, 0.005), 0.03)
        gt = min(rng.uniform(params["g_term"] - 0.005, params["g_term"] + 0.005),
                 r - 0.01)
        p["g_term"] = gt
        v = _dcf_value_float(r=r, **p)
        if v is not None and v > 0:
            values.append(v)
    if len(values) < iterations * 0.5:
        return ValuationOutcome.na(model, "simulation degenerate — check assumptions",
                                   currency)
    values.sort()

    def pct(q: float) -> float:
        return round(values[min(int(q * len(values)), len(values) - 1)], 2)

    mean_v = round(sum(values) / len(values), 2)
    prob_above = None
    if price is not None and price > 0:
        px = float(price)
        prob_above = round(sum(1 for v in values if v > px) / len(values), 4)
    lo, hi = values[0], values[-1]
    bins = 30
    width = (hi - lo) / bins if hi > lo else 1.0
    hist = []
    for b in range(bins):
        lo_b = lo + b * width
        count = sum(1 for v in values if lo_b <= v < lo_b + width)
        hist.append({"bin_low": round(lo_b, 2), "bin_high": round(lo_b + width, 2),
                     "count": count})
    mc = MonteCarloResult(
        iterations=len(values), seed=seed, mean=mean_v,
        percentiles={"p5": pct(0.05), "p25": pct(0.25), "p50": pct(0.50),
                     "p75": pct(0.75), "p95": pct(0.95)},
        prob_above_price=prob_above, histogram=hist,
    )
    node = CalcNode(
        key="monte_carlo_dcf", label="Monte Carlo DCF",
        formula="10k DCF draws over (growth ~N, margin ~Triangular, WACC ~N, g ~U)",
        result=Decimal(str(mc.percentiles["p50"])), unit=f"{currency}/share",
        explanation=f"Seeded ({seed}) and reproducible. growth σ={g_sigma:.3f}, "
                    "WACC σ=50bp, margin triangular ±15/20%.",
        method_confidence=0.8,
    )
    return ValuationOutcome(
        model=model,
        fair_value_per_share=Decimal(str(mc.percentiles["p50"])),
        currency=currency,
        low=Decimal(str(mc.percentiles["p5"])), high=Decimal(str(mc.percentiles["p95"])),
        confidence=node.confidence, outputs=mc.model_dump(), trace=node,
    )


def expected_return(history: FinancialHistory, a: AssumptionSet,
                    price: Decimal | None, fair_value: Decimal | None,
                    horizon_years: int = 5) -> ValuationOutcome:
    """Annualized expected return to fair value + dividend yield."""
    model = "expected_return"
    currency = history.currency
    if price is None or price <= 0 or fair_value is None or fair_value <= 0:
        return ValuationOutcome.na(model, "needs price and a base DCF fair value", currency)
    p = history.latest
    div_yield = 0.0
    if p:
        div, sh = p.get("dividends_paid"), p.get("shares_diluted")
        if div and sh and sh > 0:
            div_yield = float((div / sh) / price)
    price_return = (float(fair_value) / float(price)) ** (1 / horizon_years) - 1
    total = price_return + div_yield
    node = CalcNode(
        key="expected_return", label="Expected Annual Return",
        formula="E[r] = (Fair Value / Price)^(1/N) − 1 + Dividend Yield",
        inputs=[CalcInput(name="fair_value", symbol="Fair Value", value=fair_value),
                CalcInput(name="price", symbol="Price", value=price),
                CalcInput(name="horizon", symbol="N", value=Decimal(horizon_years), unit="years"),
                CalcInput(name="dividend_yield", symbol="Dividend Yield",
                          value=Decimal(str(round(div_yield, 4))), unit="%")],
        result=Decimal(str(round(total, 4))), unit="%",
        method_confidence=0.85,
    )
    return ValuationOutcome(
        model=model, currency=currency, confidence=node.confidence,
        outputs={"annualized_price_return": round(price_return, 4),
                 "dividend_yield": round(div_yield, 4),
                 "total_expected_return": round(total, 4),
                 "horizon_years": horizon_years},
        trace=node,
    )


# Model weights for the blended summary, by rough reliability of each approach.
SUMMARY_WEIGHTS = {
    "dcf_fcff": 0.30, "dcf_fcfe": 0.15, "residual_income": 0.15, "eva": 0.10,
    "ddm": 0.10, "multiples": 0.10, "comps": 0.15, "asset_based": 0.05,
    "monte_carlo_dcf": 0.15, "scenario": 0.20,
}


def summarize(outcomes: list[ValuationOutcome],
              price: Decimal | None) -> dict:
    """Football field + confidence-weighted blended intrinsic range."""
    usable = [o for o in outcomes
              if o.status == "ok" and o.fair_value_per_share is not None]
    field = [{
        "model": o.model, "fair_value": str(o.fair_value_per_share),
        "low": str(o.low) if o.low is not None else None,
        "high": str(o.high) if o.high is not None else None,
        "confidence": o.confidence,
        "weight": SUMMARY_WEIGHTS.get(o.model, 0.05),
    } for o in usable]
    skipped = [{"model": o.model, "reason": o.not_applicable_reason}
               for o in outcomes if o.status != "ok"]
    if not usable:
        return {"football_field": [], "skipped": skipped, "blended": None}

    total_w = sum(SUMMARY_WEIGHTS.get(o.model, 0.05) * o.confidence for o in usable)
    blended = sum(
        float(o.fair_value_per_share) * SUMMARY_WEIGHTS.get(o.model, 0.05) * o.confidence
        for o in usable) / total_w
    lows = [float(o.low if o.low is not None else o.fair_value_per_share) for o in usable]
    highs = [float(o.high if o.high is not None else o.fair_value_per_share) for o in usable]
    result = {
        "football_field": field, "skipped": skipped,
        "blended": {
            "fair_value": round(blended, 2),
            "range_low": round(min(lows), 2), "range_high": round(max(highs), 2),
            "method": "confidence × model-weight blend",
        },
    }
    if price is not None and price > 0 and blended > 0:
        result["blended"]["price"] = float(price)
        result["blended"]["upside_pct"] = round((blended / float(price) - 1) * 100, 2)
        result["blended"]["margin_of_safety"] = round(1 - float(price) / blended, 4)
    return result
