"""Factor scores (0–100) with documented absolute rubrics.

Sector-relative percentiles need a populated cross-section; until the local
universe is large enough these rubrics score against calibrated absolute
thresholds (documented per metric), and each pillar reports the metrics and
thresholds used — nothing is a black box.
"""
from decimal import Decimal

from pydantic import BaseModel

from app.domain.ratios.engine import MarketInputs
from app.domain.statements import derived
from app.domain.statements.history import FinancialHistory


class FactorScore(BaseModel):
    pillar: str
    score: int                    # 0-100
    components: list[dict]
    coverage: float               # fraction of metrics computable


def _scale(value: float | None, lo: float, hi: float, invert: bool = False) -> int | None:
    """Linear 0–100 between lo and hi (clamped)."""
    if value is None:
        return None
    t = (value - lo) / (hi - lo)
    t = min(max(t, 0.0), 1.0)
    if invert:
        t = 1.0 - t
    return round(t * 100)


def _pillar(name: str, metrics: list[tuple[str, float | None, int | None, str]]) -> FactorScore:
    scored = [(n, v, s, r) for n, v, s, r in metrics if s is not None]
    coverage = len(scored) / len(metrics) if metrics else 0.0
    score = round(sum(s for _, _, s, _ in scored) / len(scored)) if scored else 0
    return FactorScore(
        pillar=name, score=score, coverage=round(coverage, 2),
        components=[{"metric": n, "value": v, "score": s, "rubric": r}
                    for n, v, s, r in metrics],
    )


def _f(x: Decimal | None) -> float | None:
    return float(x) if x is not None else None


def quality(h: FinancialHistory) -> FactorScore:
    p = h.latest
    metrics: list[tuple[str, float | None, int | None, str]] = []
    if p:
        roic = None
        n_roic = derived.nopat(p)
        ic = derived.invested_capital(p)
        if n_roic and ic and ic.result != 0:
            roic = float(n_roic.result / ic.result)
        metrics.append(("roic", roic, _scale(roic, 0.0, 0.25),
                        "0% → 0, ≥25% → 100"))
        rev_by_fy = {fy: v for fy, v in h.series("revenue") if v}
        margins = [float(v / rev_by_fy[fy])
                   for fy, v in h.series("operating_income")[-5:]
                   if fy in rev_by_fy]
        stability = None
        if len(margins) >= 3:
            mean = sum(margins) / len(margins)
            var = sum((m - mean) ** 2 for m in margins) / len(margins)
            stability = var ** 0.5
        metrics.append(("margin_volatility_5y", stability,
                        _scale(stability, 0.0, 0.08, invert=True),
                        "σ(EBIT margin) 0 → 100, ≥8pp → 0"))
        ocf, ni = p.get("operating_cash_flow"), p.get("net_income")
        accrual = float((ni - ocf) / ni) if ocf is not None and ni else None
        metrics.append(("accruals_ni_gap", accrual,
                        _scale(accrual, -0.5, 0.5, invert=True),
                        "(NI−OCF)/NI: ≤−50% → 100, ≥+50% → 0"))
        de = None
        if p.total_debt is not None and (eq := p.get("total_equity")):
            de = float(p.total_debt / eq)
        metrics.append(("debt_to_equity", de, _scale(de, 0.0, 3.0, invert=True),
                        "0x → 100, ≥3x → 0"))
    return _pillar("quality", metrics)


def growth(h: FinancialHistory) -> FactorScore:
    metrics = [
        ("revenue_cagr_3y", _f(h.cagr("revenue", 3)),
         _scale(_f(h.cagr("revenue", 3)), 0.0, 0.25), "0% → 0, ≥25% → 100"),
        ("revenue_cagr_5y", _f(h.cagr("revenue", 5)),
         _scale(_f(h.cagr("revenue", 5)), 0.0, 0.20), "0% → 0, ≥20% → 100"),
        ("net_income_cagr_3y", _f(h.cagr("net_income", 3)),
         _scale(_f(h.cagr("net_income", 3)), 0.0, 0.30), "0% → 0, ≥30% → 100"),
        ("ocf_cagr_3y", _f(h.cagr("operating_cash_flow", 3)),
         _scale(_f(h.cagr("operating_cash_flow", 3)), 0.0, 0.30), "0% → 0, ≥30% → 100"),
    ]
    return _pillar("growth", metrics)


def profitability(h: FinancialHistory) -> FactorScore:
    p = h.latest
    metrics: list[tuple[str, float | None, int | None, str]] = []
    if p:
        rev = p.get("revenue")
        for key, label, hi in [("gross_profit", "gross_margin", 0.7),
                               ("operating_income", "operating_margin", 0.35),
                               ("net_income", "net_margin", 0.30)]:
            v = p.get(key)
            m = float(v / rev) if v is not None and rev else None
            metrics.append((label, m, _scale(m, 0.0, hi), f"0% → 0, ≥{hi:.0%} → 100"))
        ni, eq = p.get("net_income"), p.get("total_equity")
        roe = float(ni / eq) if ni is not None and eq else None
        metrics.append(("roe", roe, _scale(roe, 0.0, 0.35), "0% → 0, ≥35% → 100"))
    return _pillar("profitability", metrics)


def value(h: FinancialHistory, m: MarketInputs | None) -> FactorScore:
    metrics: list[tuple[str, float | None, int | None, str]] = []
    p = h.latest
    if p and m:
        ni = p.get("net_income")
        ey = float(ni / m.market_cap) if ni is not None and m.market_cap else None
        metrics.append(("earnings_yield", ey, _scale(ey, 0.0, 0.10),
                        "0% → 0, ≥10% → 100"))
        fcf = derived.free_cash_flow(p)
        fy = float(fcf.result / m.market_cap) if fcf and m.market_cap else None
        metrics.append(("fcf_yield", fy, _scale(fy, 0.0, 0.08), "0% → 0, ≥8% → 100"))
        eq = p.get("total_equity")
        pb = float(m.market_cap / eq) if eq and eq > 0 else None
        metrics.append(("price_to_book", pb, _scale(pb, 1.0, 10.0, invert=True),
                        "≤1x → 100, ≥10x → 0"))
    return _pillar("value", metrics)


def momentum(returns_6m: float | None, returns_12m: float | None,
             pct_off_52w_high: float | None) -> FactorScore:
    metrics = [
        ("return_6m", returns_6m, _scale(returns_6m, -0.30, 0.50),
         "−30% → 0, ≥+50% → 100"),
        ("return_12m", returns_12m, _scale(returns_12m, -0.40, 0.80),
         "−40% → 0, ≥+80% → 100"),
        ("pct_off_52w_high", pct_off_52w_high,
         _scale(pct_off_52w_high, -0.40, 0.0), "−40% off → 0, at high → 100"),
    ]
    return _pillar("momentum", metrics)


def risk(h: FinancialHistory, volatility_1y: float | None,
         max_drawdown_1y: float | None, altman_grade: str | None) -> FactorScore:
    """Higher score = LOWER risk."""
    metrics: list[tuple[str, float | None, int | None, str]] = [
        ("volatility_1y", volatility_1y, _scale(volatility_1y, 0.15, 0.70, invert=True),
         "≤15% ann. vol → 100, ≥70% → 0"),
        ("max_drawdown_1y", max_drawdown_1y,
         _scale(abs(max_drawdown_1y) if max_drawdown_1y is not None else None,
                0.05, 0.60, invert=True), "≤5% DD → 100, ≥60% → 0"),
    ]
    z_score_map = {"safe": 100, "grey": 50, "distress": 0}
    z = z_score_map.get(altman_grade or "", None)
    metrics.append(("altman_zone", None if z is None else float(z), z,
                    "safe → 100, grey → 50, distress → 0"))
    return _pillar("risk", metrics)


DEFAULT_WEIGHTS = {"quality": 0.25, "growth": 0.20, "profitability": 0.15,
                   "value": 0.20, "momentum": 0.10, "risk": 0.10}


def composite(pillars: list[FactorScore],
              weights: dict[str, float] | None = None) -> FactorScore:
    weights = weights or DEFAULT_WEIGHTS
    usable = [p for p in pillars if p.coverage > 0]
    total_w = sum(weights.get(p.pillar, 0) for p in usable)
    score = (round(sum(p.score * weights.get(p.pillar, 0) for p in usable) / total_w)
             if total_w else 0)
    return FactorScore(
        pillar="composite", score=score,
        coverage=round(sum(p.coverage for p in usable) / len(pillars), 2) if pillars else 0,
        components=[{"metric": p.pillar, "value": p.score,
                     "score": p.score, "rubric": f"weight {weights.get(p.pillar, 0)}"}
                    for p in pillars],
    )
