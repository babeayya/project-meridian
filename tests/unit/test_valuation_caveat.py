"""Enterprise models on financial filers are de-weighted, not suppressed.

Dropping them outright would transfer the entire blend onto the remaining
models, which are no better calibrated for a bank; the football field keeps
every number and says which ones rest on a broken assumption.
"""
from decimal import Decimal

from app.domain.valuation.advanced import summarize
from app.domain.valuation.base import ValuationOutcome
from app.services.valuation_service import (
    ENTERPRISE_MODELS,
    ENTERPRISE_ON_FINANCIAL_WARNING,
    FINANCIAL_CONFIDENCE_FACTOR,
)


def _outcome(model: str, fair_value: str, confidence: float) -> ValuationOutcome:
    return ValuationOutcome(model=model, fair_value_per_share=Decimal(fair_value),
                            confidence=confidence)


def test_caveat_halves_confidence_and_records_the_reason():
    o = _outcome("dcf_fcff", "418.73", 0.4883)
    o.caveat(ENTERPRISE_ON_FINANCIAL_WARNING, FINANCIAL_CONFIDENCE_FACTOR)
    assert o.confidence == 0.2442
    assert o.warnings == [ENTERPRISE_ON_FINANCIAL_WARNING]


def test_caveat_keeps_the_model_usable_in_the_blend():
    """status stays ok and the fair value survives — this is the difference
    between de-weighting and suppressing."""
    o = _outcome("dcf_fcff", "418.73", 0.4883)
    o.caveat("because", 0.5)
    assert o.status == "ok"
    assert o.fair_value_per_share == Decimal("418.73")
    assert summarize([o], price=None)["blended"] is not None


def test_every_dcf_derivative_is_covered():
    """scenario/monte_carlo/reverse/expected_return run the same enterprise
    forecast as dcf_fcff, so flagging dcf_fcff alone would leave most of the
    blend weight on unlabelled DCF output."""
    assert {"dcf_fcff", "eva", "scenario", "monte_carlo_dcf",
            "reverse_dcf", "expected_return"} <= ENTERPRISE_MODELS
    assert "ddm" not in ENTERPRISE_MODELS
    assert "residual_income" not in ENTERPRISE_MODELS
    assert "asset_based" not in ENTERPRISE_MODELS
    assert "multiples" not in ENTERPRISE_MODELS


def test_flagged_model_loses_weight_against_an_unflagged_one():
    flagged = _outcome("dcf_fcff", "400", 0.8)
    clean = _outcome("ddm", "100", 0.8)
    before = summarize([flagged, clean], price=None)["blended"]["fair_value"]
    flagged.caveat("because", FINANCIAL_CONFIDENCE_FACTOR)
    after = summarize([flagged, clean], price=None)["blended"]["fair_value"]
    assert after < before


def test_warnings_reach_the_football_field():
    o = _outcome("dcf_fcff", "418.73", 0.5)
    o.caveat(ENTERPRISE_ON_FINANCIAL_WARNING, FINANCIAL_CONFIDENCE_FACTOR)
    entry = summarize([o], price=None)["football_field"][0]
    assert entry["warnings"] == [ENTERPRISE_ON_FINANCIAL_WARNING]
