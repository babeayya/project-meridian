"""Golden-number DCF: every figure hand-computed independently.

Fixture: rev 1000, growth 10% flat, EBIT margin 20%, tax 25%, D&A 5%, CapEx 5%,
ΔNWC 2% of Δrev, all-equity (WACC = Ke = 4% + 1.0×5% = 9%), terminal g 2.5%,
100 shares, no net debt.
Hand calc: PV(FCFF 1-5) = 761.55, TV = 3763.30, PV(TV) = 2445.89,
EV = 3207.44 → 32.07/share.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.domain.statements.history import FinancialHistory, PeriodFinancials
from app.domain.valuation.advanced import monte_carlo_dcf, reverse_dcf, scenarios, sensitivity
from app.domain.valuation.base import AssumptionSet, WaccInputs
from app.domain.valuation.dcf import dcf_fcff
from app.domain.valuation.equity_models import ddm


def history_fixture() -> FinancialHistory:
    years = []
    rev = Decimal(700)
    for fy in range(2021, 2026):
        rev = rev * Decimal("1.1")
        years.append(PeriodFinancials(
            fiscal_year=fy, period_end=date(fy, 12, 31), currency="USD",
            items={
                "revenue": rev.quantize(Decimal("0.01")),
                "operating_income": (rev * Decimal("0.2")).quantize(Decimal("0.01")),
                "net_income": (rev * Decimal("0.15")).quantize(Decimal("0.01")),
                "pretax_income": (rev * Decimal("0.2")).quantize(Decimal("0.01")),
                "income_tax": (rev * Decimal("0.05")).quantize(Decimal("0.01")),
                "total_equity": Decimal(2000), "total_assets": Decimal(4000),
                "shares_diluted": Decimal(100),
            }))
    # pin latest revenue to exactly 1000 for the golden numbers
    years[-1].items["revenue"] = Decimal(1000)
    return FinancialHistory(currency="USD", annual=years)


def assumptions_fixture() -> AssumptionSet:
    return AssumptionSet(
        forecast_years=5,
        revenue_growth=[Decimal("0.10")] * 5,
        ebit_margin=[Decimal("0.20")] * 5,
        tax_rate=Decimal("0.25"),
        da_pct_revenue=Decimal("0.05"),
        capex_pct_revenue=Decimal("0.05"),
        nwc_pct_revenue_delta=Decimal("0.02"),
        terminal_growth=Decimal("0.025"),
        shares_diluted=Decimal(100),
        net_debt=Decimal(0),
        wacc=WaccInputs(risk_free_rate=Decimal("0.04"), beta=Decimal("1.0"),
                        equity_risk_premium=Decimal("0.05"),
                        tax_rate=Decimal("0.25"),
                        market_cap=Decimal(3000), total_debt=Decimal(0)),
    )


def test_dcf_fcff_golden_number():
    out = dcf_fcff(history_fixture(), assumptions_fixture(), Decimal(25))
    assert out.status == "ok"
    assert out.fair_value_per_share == pytest.approx(Decimal("32.07"), abs=Decimal("0.05"))
    assert Decimal(out.outputs["wacc"]) == Decimal("0.09")
    assert Decimal(out.outputs["pv_explicit"]) == pytest.approx(
        Decimal("761.55"), abs=Decimal("0.5"))
    assert Decimal(out.outputs["pv_terminal"]) == pytest.approx(
        Decimal("2445.89"), abs=Decimal("1.5"))
    # trace must expose formula → substitution → result at every level
    assert out.trace is not None
    wacc_node = out.trace.find("wacc")
    assert wacc_node is not None and "Ke" in wacc_node.formula
    y1 = out.trace.find("dcf.year1.fcff")
    assert y1 is not None and y1.result == pytest.approx(Decimal("163"), abs=Decimal("0.01"))


def test_dcf_terminal_undefined_when_wacc_below_growth():
    a = assumptions_fixture()
    a.terminal_growth = Decimal("0.10")  # ≥ 9% WACC
    out = dcf_fcff(history_fixture(), a, None)
    assert out.status == "not_applicable"
    assert "terminal" in out.not_applicable_reason.lower()


def test_ddm_not_applicable_without_dividends():
    out = ddm(history_fixture(), assumptions_fixture(), Decimal(25))
    assert out.status == "not_applicable"
    assert "dividend" in out.not_applicable_reason


def test_reverse_dcf_recovers_known_growth():
    """Price the company with the engine at 10% growth, then reverse-solve:
    implied growth must come back ≈10%."""
    h, a = history_fixture(), assumptions_fixture()
    fair = dcf_fcff(h, a, None).fair_value_per_share
    out = reverse_dcf(h, a, fair)
    assert out.status == "ok"
    assert out.outputs["implied_growth"] == pytest.approx(0.10, abs=0.005)


def test_sensitivity_grid_monotonic_in_wacc():
    grid = sensitivity(history_fixture(), assumptions_fixture(), steps=5)
    assert grid is not None
    mid_row = grid.matrix[2]
    values = [float(v) for v in mid_row if v]
    assert values == sorted(values, reverse=True)  # higher WACC → lower value


def test_scenarios_probability_weighting():
    out = scenarios(history_fixture(), assumptions_fixture(), Decimal(25))
    assert out.status == "ok"
    cases = {s["name"]: Decimal(s["fair_value"]) for s in out.outputs["scenarios"]}
    assert cases["bear"] < cases["base"] < cases["bull"]
    assert out.low == cases["bear"] and out.high == cases["bull"]


def test_monte_carlo_reproducible_by_seed():
    h, a = history_fixture(), assumptions_fixture()
    r1 = monte_carlo_dcf(h, a, Decimal(25), iterations=2000, seed=7)
    r2 = monte_carlo_dcf(h, a, Decimal(25), iterations=2000, seed=7)
    assert r1.outputs["percentiles"] == r2.outputs["percentiles"]
    p = r1.outputs["percentiles"]
    assert p["p5"] < p["p50"] < p["p95"]
