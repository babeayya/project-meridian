from decimal import Decimal

from app.domain.calc.trace import CalcInput, CalcNode, Provenance


def _cost_of_equity() -> CalcNode:
    rf = CalcInput(
        name="risk_free_rate", symbol="Rf", value=Decimal("0.0428"), unit="%",
        source=Provenance(provider="FRED", series="DGS10", as_of="2026-07-08"),
        confidence=0.98,
    )
    beta = CalcInput(
        name="levered_beta", symbol="β", value=Decimal("1.04"),
        source=Provenance(provider="computed", method="5y monthly OLS vs SPX"),
        confidence=0.90,
    )
    erp = CalcInput(
        name="equity_risk_premium", symbol="ERP", value=Decimal("0.05"), unit="%",
        source=Provenance(provider="assumption", editable=True),
        confidence=0.80,
    )
    result = rf.value + beta.value * erp.value  # 0.0428 + 1.04*0.05 = 0.0948
    return CalcNode(
        key="wacc.cost_of_equity", label="Cost of Equity (CAPM)",
        formula="Ke = Rf + β × ERP",
        inputs=[rf, beta, erp], result=result, unit="%",
        explanation="CAPM with 10-year treasury as the risk-free proxy.",
    )


def test_result_and_substitution():
    node = _cost_of_equity()
    assert node.result == Decimal("0.0948")
    # substitution preserves the LHS and replaces symbols with values
    assert node.substitution.startswith("Ke = ")
    assert "4.28%" in node.substitution
    assert "1.04" in node.substitution
    assert "5.00%" in node.substitution
    assert node.substitution.endswith("= 9.48%")


def test_confidence_rolls_up_from_weakest_input():
    node = _cost_of_equity()
    assert node.confidence == 0.80  # min of (0.98, 0.90, 0.80) × 1.0


def test_intermediates_propagate_confidence_and_find():
    ke = _cost_of_equity()
    wacc = CalcNode(
        key="wacc", label="WACC",
        formula="WACC = wE × Ke + wD × Kd × (1 − t)",
        intermediates=[ke], result=Decimal("0.0913"), unit="%",
        method_confidence=0.95,
    )
    assert wacc.confidence == round(0.80 * 0.95, 4)
    assert wacc.find("wacc.cost_of_equity") is ke
    assert wacc.find("missing") is None


def test_trace_serializes_full_tree():
    ke = _cost_of_equity()
    data = ke.to_dict()
    assert data["formula"] == "Ke = Rf + β × ERP"
    assert data["confidence"] == 0.80
    assert data["inputs"][0]["source"]["provider"] == "FRED"
