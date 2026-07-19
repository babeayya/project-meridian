"""Derived metrics, ratios, DuPont, and classic scores on crafted fixtures."""
from datetime import date
from decimal import Decimal

import pytest

from app.domain.ratios.engine import MarketInputs, all_ratios, dupont
from app.domain.scores.classic import altman_z, beneish_m, piotroski_f
from app.domain.statements import derived
from app.domain.statements.history import FinancialHistory, PeriodFinancials


def period(fy: int, **items) -> PeriodFinancials:
    return PeriodFinancials(fiscal_year=fy, period_end=date(fy, 12, 31),
                            currency="USD",
                            items={k: Decimal(str(v)) for k, v in items.items()})


CUR = period(
    2025, revenue=1000, cost_of_revenue=600, gross_profit=400,
    operating_income=200, pretax_income=190, income_tax=38, net_income=152,
    interest_expense=10, depreciation_amortization=50, capex=60,
    operating_cash_flow=210, change_in_working_capital=-5,
    current_assets=500, current_liabilities=250, inventory=100,
    cash_and_equivalents=150, short_term_investments=50,
    receivables=120, accounts_payable=80,
    total_assets=2000, total_liabilities=1200, total_equity=800,
    retained_earnings=400, short_term_debt=100, long_term_debt=400,
    net_ppe=900, goodwill=100, intangibles=50, shares_diluted=100,
    sga_expense=120,
)
PRIOR = period(
    2024, revenue=900, cost_of_revenue=560, gross_profit=340,
    operating_income=170, pretax_income=162, income_tax=32, net_income=130,
    depreciation_amortization=45, capex=55, operating_cash_flow=180,
    current_assets=430, current_liabilities=240, inventory=95,
    receivables=100, total_assets=1850, total_liabilities=1150,
    total_equity=700, long_term_debt=420, net_ppe=850, shares_diluted=102,
    sga_expense=115,
)


def test_derived_metrics():
    assert derived.ebitda(CUR).result == Decimal(250)
    tax = derived.effective_tax_rate(CUR)
    assert tax.result == Decimal("0.2000")           # 38/190
    assert derived.nopat(CUR).result == Decimal("160.00")   # 200×0.8
    assert derived.net_debt(CUR).result == Decimal(300)     # 500−150−50
    assert derived.invested_capital(CUR).result == Decimal(1150)  # 800+500−150
    # FCFF = 160 + 50 − 60 + (−5) = 145
    assert derived.fcff(CUR).result == Decimal("145.00")
    assert derived.free_cash_flow(CUR).result == Decimal(150)     # 210−60


def test_tax_rate_clamped():
    weird = period(2025, income_tax=90, pretax_income=100)
    node = derived.effective_tax_rate(weird)
    assert node.result == Decimal("0.4000")
    assert node.assumptions  # clamp documented in the trace


def test_ratios_and_dupont():
    market = MarketInputs(price=Decimal(30), shares=Decimal(100),
                          market_cap=Decimal(3000))
    groups = all_ratios(CUR, PRIOR, market)
    assert groups["liquidity"]["current_ratio"].result == Decimal(2)
    assert groups["profitability"]["roe"].result == Decimal("0.19")      # 152/800
    assert groups["leverage"]["debt_to_equity"].result == Decimal("0.625")
    assert groups["market"]["pe"].result == pytest.approx(
        Decimal("19.7368"), abs=Decimal("0.001"))                        # 30/1.52
    # DuPont 5-level must reproduce ROE
    node = dupont(FinancialHistory(currency="USD", annual=[PRIOR, CUR]), levels=5)
    assert node.result == pytest.approx(Decimal("0.19"), abs=Decimal("0.0002"))


def test_altman_z_variants_and_guards():
    na = altman_z(CUR, Decimal(3000), is_financial=True, is_manufacturer=False)
    assert na.not_applicable_reason is not None
    z = altman_z(CUR, Decimal(3000), is_financial=False, is_manufacturer=True)
    assert z.grade in ("safe", "grey", "distress")
    # X1=250/2000=.125 X2=.2 X3=.1 X4=3000/1200=2.5 X5=.5
    # Z = 1.2(.125)+1.4(.2)+3.3(.1)+0.6(2.5)+1.0(.5) = .15+.28+.33+1.5+.5 = 2.76
    assert z.value == pytest.approx(Decimal("2.76"), abs=Decimal("0.001"))
    assert z.grade == "grey"


def test_piotroski_counts_checks():
    r = piotroski_f(CUR, PRIOR)
    assert 0 <= int(r.value) <= 9
    names = {c["name"] for c in r.components}
    assert len(names) == 9
    # positive ROA, positive OCF, improving ROA, OCF>NI, fewer shares → all pass
    passed = {c["name"] for c in r.components if c["passed"]}
    assert {"ROA positive", "OCF positive", "Accruals (OCF > NI)",
            "No dilution"} <= passed


def test_beneish_produces_grade():
    r = beneish_m(CUR, PRIOR)
    assert r is not None
    assert r.grade in ("clean", "flag")
    assert len(r.components) == 8
