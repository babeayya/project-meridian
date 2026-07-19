from decimal import Decimal

from test_dcf_golden import assumptions_fixture, history_fixture

from app.domain.scores import factors
from app.domain.valuation.relative import YearEndPrice, historical_multiples


def test_historical_multiples_mean_reversion():
    h = history_fixture()
    # constant 15% net margin and constant P/E of ~20 at each year end
    prices = [YearEndPrice(fiscal_year=p.fiscal_year,
                           price=(p.get("net_income") / Decimal(100)) * 20)
              for p in h.annual]
    out = historical_multiples(h, assumptions_fixture(), Decimal(25), prices)
    assert out.status == "ok"
    # latest NI = 150 (1000×15%) ... EPS 1.5 × P/E 20 → around 30/share among bases
    assert Decimal("20") < out.fair_value_per_share < Decimal("40")
    assert out.outputs["multiples"]


def test_historical_multiples_needs_overlap():
    out = historical_multiples(history_fixture(), assumptions_fixture(),
                               Decimal(25), [])
    assert out.status == "not_applicable"


def test_factor_pillars_and_composite():
    h = history_fixture()
    q = factors.quality(h)
    g = factors.growth(h)
    assert 0 <= q.score <= 100 and q.coverage > 0
    # fixture CAGR ≈ 5.7% (final year pinned to 1000 for the DCF golden test):
    # rubric maps that into the 20s-30s with 3 of 4 metrics available
    assert 15 <= g.score <= 45 and g.coverage == 0.75
    comp = factors.composite([q, g])
    assert 0 <= comp.score <= 100
    assert comp.pillar == "composite"


def test_momentum_pillar_handles_missing_data():
    m = factors.momentum(None, None, None)
    assert m.score == 0 and m.coverage == 0
