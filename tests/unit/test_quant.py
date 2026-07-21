import math
import random
from datetime import date, timedelta

from app.domain.quant import engine


def make_series(n: int = 400, seed: int = 3, drift: float = 0.0005,
                vol: float = 0.02) -> engine.PriceSeries:
    rng = random.Random(seed)
    px, dates, closes = 100.0, [], []
    d = date(2024, 1, 1)
    for _ in range(n):
        px *= math.exp(rng.gauss(drift, vol))
        d += timedelta(days=1)
        dates.append(d)
        closes.append(round(px, 4))
    return engine.PriceSeries(dates=dates, closes=closes)


def test_beta_of_series_against_itself_is_one():
    s = make_series()
    rs = engine.daily_log_returns(s)
    model = engine.capm(rs, rs, rf_annual=0.04)
    assert model is not None
    assert abs(model.beta - 1.0) < 1e-9
    assert model.r_squared > 0.999


def test_performance_metrics_sane():
    s = make_series(drift=0.001)
    bench = make_series(seed=9, drift=0.0004)
    perf = engine.performance(s, bench, rf_annual=0.04)
    assert perf is not None
    assert perf.annualized_volatility > 0
    assert -1.0 <= perf.max_drawdown <= 0
    assert perf.beta is not None
    assert perf.tracking_error is not None and perf.tracking_error > 0


def test_var_ordering_and_cvar_beyond_var():
    s = make_series()
    r = engine.risk(s)
    assert r is not None
    assert r.var_99_hist <= r.var_95_hist < 0
    assert r.cvar_95 <= r.var_95_hist    # expected shortfall at least as severe
    assert r.cvar_99 <= r.var_99_hist


def test_rolling_series_lengths():
    s = make_series(n=300)
    bench = make_series(n=300, seed=11)
    betas = engine.rolling_beta(s, bench, window=90)
    sharpes = engine.rolling_sharpe(s, 0.04, window=90)
    assert len(betas) > 100 and len(sharpes) > 100
    assert all("date" in b and "beta" in b for b in betas[:5])


def test_momentum_stats():
    s = make_series(n=300, drift=0.001)
    m = engine.momentum_stats(s)
    assert m["return_6m"] is not None
    assert m["return_12m"] is not None
    assert m["pct_off_52w_high"] is not None and m["pct_off_52w_high"] <= 0


def test_short_benchmark_overlap_yields_no_beta():
    """A truncated benchmark response (Yahoo throttling a 2y request down to a
    couple of months) collapses the overlap. A fit that short is biased, not
    just noisy — JPM measured 0.23 over 60 sessions against 0.95 over 499 —
    and it feeds WACC, so no beta is better than that one."""
    s = make_series(n=400)
    truncated = engine.PriceSeries(dates=s.dates[-70:], closes=s.closes[-70:])
    perf = engine.performance(s, truncated, rf_annual=0.04)
    assert perf is not None                 # non-beta metrics still stand
    assert perf.annualized_volatility > 0
    assert perf.beta is None
    assert perf.treynor is None and perf.jensen_alpha is None


def test_full_benchmark_overlap_still_reports_beta():
    s = make_series(n=400)
    bench = make_series(n=400, seed=9)
    perf = engine.performance(s, bench, rf_annual=0.04)
    assert perf is not None and perf.beta is not None
