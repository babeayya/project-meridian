import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_session, get_valuation_service
from app.core.errors import EntityNotFound
from app.repositories.valuation import ValuationRepository
from app.schemas.common import envelope
from app.services.valuation_service import ValuationService

router = APIRouter(tags=["valuations"])

ValuationDep = Annotated[ValuationService, Depends(get_valuation_service)]


class RunRequest(BaseModel):
    assumption_set_id: uuid.UUID | None = None
    overrides: dict | None = None


@router.get("/companies/{company_id}/assumptions")
async def default_assumptions(company_id: uuid.UUID, service: ValuationDep) -> dict:
    assumptions, derivation = await service.build_default_assumptions(company_id)
    return envelope({"assumptions": assumptions.model_dump(mode="json"),
                     "derivation": derivation})


@router.get("/companies/{company_id}/valuations/summary")
async def valuation_summary(company_id: uuid.UUID, service: ValuationDep) -> dict:
    """Runs every applicable model fresh and returns the football field +
    blended intrinsic range + margin of safety."""
    return envelope(await service.run_all(company_id))


# NOTE: registered before the generic /{model} route so "sensitivity" is not
# captured as a model name.
@router.post("/companies/{company_id}/valuations/sensitivity")
async def sensitivity(
    company_id: uuid.UUID, service: ValuationDep,
    body: RunRequest | None = None,
    steps: Annotated[int, Query(ge=3, le=9)] = 5,
) -> dict:
    body = body or RunRequest()
    return envelope(await service.sensitivity_grid(
        company_id, body.assumption_set_id, steps))


@router.post("/companies/{company_id}/valuations/{model}")
async def run_valuation(
    company_id: uuid.UUID, model: str, service: ValuationDep,
    body: RunRequest | None = None,
) -> dict:
    body = body or RunRequest()
    model = model.replace("-", "_")
    outcome, run_id = await service.run_model(
        company_id, model, body.assumption_set_id, body.overrides)
    data = outcome.model_dump(mode="json")
    if outcome.trace is not None:
        data["trace"] = outcome.trace.to_dict()
    data["run_id"] = str(run_id)
    return envelope(data)


@router.get("/valuations/runs/{run_id}")
async def get_run(run_id: uuid.UUID, session=Depends(get_session)) -> dict:
    repo = ValuationRepository(session)
    run = await repo.get_run(run_id)
    if run is None:
        raise EntityNotFound(f"Valuation run {run_id} not found")
    return envelope({
        "id": str(run.id), "company_id": str(run.company_id), "model": run.model,
        "status": run.status, "not_applicable_reason": run.not_applicable_reason,
        "fair_value_per_share": str(run.fair_value_per_share) if run.fair_value_per_share else None,
        "currency": run.currency,
        "price_at_run": str(run.price_at_run) if run.price_at_run else None,
        "upside_pct": run.upside_pct,
        "low": str(run.low) if run.low else None,
        "high": str(run.high) if run.high else None,
        "confidence": run.confidence, "outputs": run.outputs, "trace": run.trace,
        "engine_version": run.engine_version,
        "created_at": run.created_at.isoformat(),
    })
