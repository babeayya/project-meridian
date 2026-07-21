"""Visualization endpoints: render-ready series shaped from engine output."""
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_analysis_service, get_financials_service, get_session
from app.core.errors import EntityNotFound
from app.domain.valuation.advanced import summarize
from app.domain.valuation.base import ValuationOutcome
from app.repositories.valuation import ValuationRepository
from app.schemas.common import envelope
from app.services.analysis import AnalysisService
from app.services.financials import FinancialsService

router = APIRouter(prefix="/charts", tags=["charts"])

FinDep = Annotated[FinancialsService, Depends(get_financials_service)]
AnalysisDep = Annotated[AnalysisService, Depends(get_analysis_service)]


@router.get("/{company_id}/financial-history")
async def financial_history(
    company_id: uuid.UUID, financials: FinDep,
    metrics: Annotated[str, Query()] = "revenue,operating_income,net_income,operating_cash_flow",
) -> dict:
    history = await financials.history(company_id)
    if not history.annual:
        raise EntityNotFound("No fundamentals ingested")
    keys = [m.strip() for m in metrics.split(",")]
    return envelope({
        "currency": history.currency,
        "years": [p.fiscal_year for p in history.annual],
        "series": {k: [str(v) if (v := p.get(k)) is not None else None
                       for p in history.annual] for k in keys},
    })


@router.get("/{company_id}/margins")
async def margins(company_id: uuid.UUID, financials: FinDep) -> dict:
    history = await financials.history(company_id)
    if not history.annual:
        raise EntityNotFound("No fundamentals ingested")
    out = {"years": [p.fiscal_year for p in history.annual],
           "gross": [], "operating": [], "net": []}
    for p in history.annual:
        rev = p.get("revenue")
        for key, name in [("gross_profit", "gross"), ("operating_income", "operating"),
                          ("net_income", "net")]:
            v = p.get(key)
            out[name].append(round(float(v / rev), 4) if v is not None and rev else None)
    return envelope(out)


@router.get("/{company_id}/radar-scores")
async def radar_scores(company_id: uuid.UUID, analysis: AnalysisDep) -> dict:
    scores = await analysis.scores(company_id)
    return envelope({
        "axes": [{"pillar": name, "score": s["score"], "coverage": s["coverage"]}
                 for name, s in scores["factors"].items()],
        "composite": scores["composite"]["score"],
    })


@router.get("/{company_id}/dcf-waterfall")
async def dcf_waterfall(company_id: uuid.UUID, session=Depends(get_session),
                        run_id: Annotated[uuid.UUID | None, Query()] = None) -> dict:
    repo = ValuationRepository(session)
    run = await repo.get_run(run_id) if run_id else next(
        (r for r in await repo.latest_runs(company_id) if r.model == "dcf_fcff"), None)
    if run is None or run.status != "ok":
        raise EntityNotFound("No successful dcf_fcff run — POST /valuations/dcf-fcff first")
    o = run.outputs
    ev = Decimal(o["ev"])
    net_debt = Decimal(o.get("net_debt", "0"))
    # net_debt > 0 subtracts from EV (levered); net_debt < 0 is a net-cash
    # position that adds to EV — label and color must follow the sign.
    debt_block = (
        {"label": "Net debt", "value": str(-net_debt), "type": "subtract"}
        if net_debt >= 0 else
        {"label": "Net cash", "value": str(-net_debt), "type": "add"}
    )
    blocks = [
        {"label": "PV of explicit FCFF", "value": o["pv_explicit"], "type": "add"},
        {"label": "PV of terminal value", "value": o["pv_terminal"], "type": "add"},
        {"label": "Enterprise value", "value": o["ev"], "type": "subtotal"},
        debt_block,
        {"label": "Equity value", "value": o["equity_value"], "type": "subtotal"},
        {"label": "Fair value / share",
         "value": str(run.fair_value_per_share), "type": "result"},
    ]
    return envelope({"run_id": str(run.id), "currency": run.currency,
                     "blocks": blocks, "terminal_share_of_ev": o.get("terminal_share_of_ev"),
                     "ev": str(ev)})


@router.get("/{company_id}/valuation-bridge")
async def valuation_bridge(company_id: uuid.UUID, session=Depends(get_session)) -> dict:
    """Football field: latest run per model vs current price."""
    repo = ValuationRepository(session)
    runs = await repo.latest_runs(company_id)
    ok = [r for r in runs if r.status == "ok" and r.fair_value_per_share]
    if not ok:
        raise EntityNotFound("No valuation runs — POST /valuations/... first")
    # Blend here rather than in the client. The header used to reduce these
    # runs itself weighting by confidence alone, which silently dropped the
    # per-model weights and disagreed with /valuations/summary on the same
    # inputs (JPM: 253.89 against 297.88) — two different headline numbers for
    # one labelled concept. summarize() is the single definition.
    blended = summarize(
        [ValuationOutcome(model=r.model, fair_value_per_share=r.fair_value_per_share,
                          currency=r.currency, low=r.low, high=r.high,
                          confidence=r.confidence)
         for r in ok],
        price=None,
    )["blended"]
    return envelope({
        "price": str(ok[0].price_at_run) if ok[0].price_at_run else None,
        "currency": ok[0].currency,
        "blended": blended,
        "models": [{"model": r.model, "fair_value": str(r.fair_value_per_share),
                    "low": str(r.low) if r.low else None,
                    "high": str(r.high) if r.high else None,
                    "confidence": r.confidence, "upside_pct": r.upside_pct}
                   for r in ok],
        "skipped": [{"model": r.model, "reason": r.not_applicable_reason}
                    for r in runs if r.status != "ok"],
    })


@router.get("/{company_id}/monte-carlo-distribution")
async def mc_distribution(company_id: uuid.UUID, session=Depends(get_session),
                          run_id: Annotated[uuid.UUID | None, Query()] = None) -> dict:
    repo = ValuationRepository(session)
    run = await repo.get_run(run_id) if run_id else next(
        (r for r in await repo.latest_runs(company_id)
         if r.model == "monte_carlo_dcf"), None)
    if run is None or run.status != "ok":
        raise EntityNotFound("No monte_carlo_dcf run — POST /valuations/monte-carlo-dcf first")
    return envelope({"run_id": str(run.id), "currency": run.currency,
                     "price_at_run": str(run.price_at_run) if run.price_at_run else None,
                     **run.outputs})
