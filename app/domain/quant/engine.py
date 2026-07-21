"""Quant engine: returns, CAPM, performance ratios, risk metrics, rolling
series. Pure float math over aligned daily close series."""
import math
from datetime import date

from pydantic import BaseModel, Field

TRADING_DAYS = 252

# Overlapping daily observations required before a beta is reported. capm()
# will fit 60, but a fit that short is biased rather than merely noisy — the
# same stock can measure 0.23 over 60 sessions and 0.95 over 499 — so anything
# consuming beta for pricing must hold to this floor.
MIN_BETA_OBSERVATIONS = 250


class PriceSeries(BaseModel):
    dates: list[date]
    closes: list[float]


def daily_log_returns(s: PriceSeries) -> list[float]:
    return [math.log(b / a) for a, b in zip(s.closes, s.closes[1:], strict=False)
            if a > 0 and b > 0]


def align(a: PriceSeries, b: PriceSeries) -> tuple[list[float], list[float]]:
    """Align two series on common dates, return their daily log returns."""
    b_map = dict(zip(b.dates, b.closes, strict=True))
    common = [(d, ca, b_map[d]) for d, ca in zip(a.dates, a.closes, strict=True)
              if d in b_map]
    ra = [math.log(y / x) for (_, x, _), (_, y, _) in zip(common, common[1:], strict=False)
          if x > 0 and y > 0]
    rb = [math.log(y / x) for (_, _, x), (_, _, y) in zip(common, common[1:], strict=False)
          if x > 0 and y > 0]
    return ra, rb


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def _cov(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / (len(xs) - 1)


class CapmResult(BaseModel):
    beta: float
    alpha_annual: float               # Jensen's alpha
    r_squared: float
    observations: int
    formula: str = "Ri = α + β·Rm + ε (OLS on daily log returns)"


def capm(stock: list[float], bench: list[float], rf_annual: float) -> CapmResult | None:
    n = min(len(stock), len(bench))
    if n < 60:
        return None
    s, b = stock[-n:], bench[-n:]
    var_b = _std(b) ** 2
    if var_b == 0:
        return None
    beta = _cov(s, b) / var_b
    rf_d = rf_annual / TRADING_DAYS
    alpha_d = _mean(s) - rf_d - beta * (_mean(b) - rf_d)
    ss_tot = sum((x - _mean(s)) ** 2 for x in s)
    resid = [x - (alpha_d + rf_d + beta * (y - rf_d)) for x, y in zip(s, b, strict=True)]
    ss_res = sum(e ** 2 for e in resid)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return CapmResult(beta=round(beta, 4), alpha_annual=round(alpha_d * TRADING_DAYS, 4),
                      r_squared=round(r2, 4), observations=n)


class PerformanceMetrics(BaseModel):
    window_days: int
    annualized_return: float
    annualized_volatility: float
    sharpe: float | None
    sortino: float | None
    treynor: float | None
    jensen_alpha: float | None
    information_ratio: float | None
    tracking_error: float | None
    max_drawdown: float
    calmar: float | None
    beta: float | None
    formulas: dict[str, str] = Field(default_factory=lambda: {
        "sharpe": "(E[R] − Rf) / σ, annualized",
        "sortino": "(E[R] − Rf) / downside σ, annualized",
        "treynor": "(E[R] − Rf) / β",
        "jensen_alpha": "E[R] − [Rf + β(E[Rm] − Rf)], annualized",
        "information_ratio": "E[R − Rm] / tracking error",
        "tracking_error": "σ(R − Rm), annualized",
        "max_drawdown": "max peak-to-trough decline of cumulative series",
        "calmar": "annualized return / |max drawdown|",
    })


def max_drawdown(closes: list[float]) -> float:
    peak, mdd = float("-inf"), 0.0
    for c in closes:
        peak = max(peak, c)
        if peak > 0:
            mdd = min(mdd, c / peak - 1)
    return round(mdd, 4)


def performance(stock: PriceSeries, bench: PriceSeries | None,
                rf_annual: float) -> PerformanceMetrics | None:
    rs = daily_log_returns(stock)
    if len(rs) < 60:
        return None
    ann_ret = _mean(rs) * TRADING_DAYS
    ann_vol = _std(rs) * math.sqrt(TRADING_DAYS)
    rf_d = rf_annual / TRADING_DAYS
    excess = [r - rf_d for r in rs]
    sharpe = (_mean(excess) * TRADING_DAYS) / ann_vol if ann_vol else None
    downside = [r for r in excess if r < 0]
    dvol = _std(downside) * math.sqrt(TRADING_DAYS) if len(downside) >= 2 else None
    sortino = (_mean(excess) * TRADING_DAYS) / dvol if dvol else None
    mdd = max_drawdown(stock.closes)
    calmar = ann_ret / abs(mdd) if mdd else None

    beta = treynor = jensen = ir = te = None
    if bench is not None:
        ra, rb = align(stock, bench)
        model = capm(ra, rb, rf_annual)
        # A truncated benchmark response collapses the overlap; reporting a
        # beta off the remainder would understate systematic risk badly.
        if model and model.observations >= MIN_BETA_OBSERVATIONS:
            beta = model.beta
            jensen = model.alpha_annual
            if beta:
                treynor = round((_mean(excess) * TRADING_DAYS) / beta, 4)
            n = min(len(ra), len(rb))
            active = [x - y for x, y in zip(ra[-n:], rb[-n:], strict=True)]
            te_v = _std(active) * math.sqrt(TRADING_DAYS)
            te = round(te_v, 4)
            ir = round((_mean(active) * TRADING_DAYS) / te_v, 4) if te_v else None
    return PerformanceMetrics(
        window_days=len(rs),
        annualized_return=round(ann_ret, 4), annualized_volatility=round(ann_vol, 4),
        sharpe=round(sharpe, 4) if sharpe is not None else None,
        sortino=round(sortino, 4) if sortino is not None else None,
        treynor=treynor, jensen_alpha=jensen,
        information_ratio=ir, tracking_error=te,
        max_drawdown=mdd, calmar=round(calmar, 4) if calmar is not None else None,
        beta=beta,
    )


class RiskMetrics(BaseModel):
    var_95_hist: float
    var_99_hist: float
    var_95_parametric: float
    cvar_95: float
    cvar_99: float
    annualized_volatility: float
    method_notes: dict[str, str] = Field(default_factory=lambda: {
        "historical": "empirical daily-return percentile",
        "parametric": "μ + z·σ under normality",
        "cvar": "mean loss beyond the VaR threshold (expected shortfall)",
        "sign": "reported as negative daily returns",
    })


def risk(stock: PriceSeries) -> RiskMetrics | None:
    rs = sorted(daily_log_returns(stock))
    if len(rs) < 100:
        return None

    def var_hist(q: float) -> float:
        return rs[max(int(q * len(rs)) - 1, 0)]

    def cvar(q: float) -> float:
        cut = max(int(q * len(rs)), 1)
        tail = rs[:cut]
        return _mean(tail)

    mu, sigma = _mean(rs), _std(rs)
    return RiskMetrics(
        var_95_hist=round(var_hist(0.05), 4), var_99_hist=round(var_hist(0.01), 4),
        var_95_parametric=round(mu - 1.6449 * sigma, 4),
        cvar_95=round(cvar(0.05), 4), cvar_99=round(cvar(0.01), 4),
        annualized_volatility=round(sigma * math.sqrt(TRADING_DAYS), 4),
    )


def rolling_beta(stock: PriceSeries, bench: PriceSeries,
                 window: int = 90) -> list[dict]:
    ra, rb = align(stock, bench)
    n = min(len(ra), len(rb))
    ra, rb = ra[-n:], rb[-n:]
    dates = stock.dates[-n:]
    out = []
    for i in range(window, n):
        ws, wb = ra[i - window:i], rb[i - window:i]
        var_b = _std(wb) ** 2
        if var_b:
            out.append({"date": dates[i].isoformat(),
                        "beta": round(_cov(ws, wb) / var_b, 4)})
    return out


def rolling_sharpe(stock: PriceSeries, rf_annual: float, window: int = 90) -> list[dict]:
    rs = daily_log_returns(stock)
    dates = stock.dates[1:]
    rf_d = rf_annual / TRADING_DAYS
    out = []
    for i in range(window, len(rs)):
        w = rs[i - window:i]
        vol = _std(w) * math.sqrt(TRADING_DAYS)
        if vol:
            out.append({"date": dates[i].isoformat(),
                        "sharpe": round((_mean(w) - rf_d) * TRADING_DAYS / vol, 4)})
    return out


def momentum_stats(stock: PriceSeries) -> dict:
    closes = stock.closes
    out: dict[str, float | None] = {"return_6m": None, "return_12m": None,
                                    "pct_off_52w_high": None}
    if len(closes) >= 126 and closes[-126] > 0:
        out["return_6m"] = round(closes[-1] / closes[-126] - 1, 4)
    if len(closes) >= 252 and closes[-252] > 0:
        out["return_12m"] = round(closes[-1] / closes[-252] - 1, 4)
        high = max(closes[-252:])
        if high > 0:
            out["pct_off_52w_high"] = round(closes[-1] / high - 1, 4)
    return out
