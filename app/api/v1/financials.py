import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_financials_service, get_fundamentals_ingestion, get_session
from app.core.errors import EntityNotFound
from app.domain.statements.taxonomy import label_of, statement_of
from app.repositories.actions import ActionsRepository
from app.schemas.common import envelope
from app.services.financials import FinancialsService
from app.services.ingestion.fundamentals import FundamentalsIngestionService

router = APIRouter(prefix="/companies", tags=["financials"])


@router.post("/{company_id}/fundamentals/refresh")
async def refresh_fundamentals(
    company_id: uuid.UUID,
    ingestion: Annotated[FundamentalsIngestionService, Depends(get_fundamentals_ingestion)],
) -> dict:
    result = await ingestion.refresh(company_id)
    return envelope(result.model_dump(mode="json"),
                    sources=sorted(set(result.sources.values())),
                    warnings=result.warnings)


@router.get("/{company_id}/financials")
async def get_financials(
    company_id: uuid.UUID,
    financials: Annotated[FinancialsService, Depends(get_financials_service)],
    statement: Annotated[str, Query()] = "all",       # income|balance|cashflow|all
    period: Annotated[str, Query()] = "annual",       # annual|quarterly
    limit: Annotated[int, Query(ge=1, le=12)] = 10,
) -> dict:
    history = await financials.history(company_id)
    periods = history.annual if period == "annual" else history.quarterly
    if not periods:
        raise EntityNotFound(
            f"No {period} statements ingested — "
            f"POST /companies/{company_id}/fundamentals/refresh first")
    out = []
    for p in periods[-limit:]:
        items = {
            k: {"label": label_of(k), "value": str(v),
                "statement": (statement_of(k) or "other")}
            for k, v in sorted(p.items.items())
            if statement == "all" or (statement_of(k) or "") == statement
        }
        out.append({"fiscal_year": p.fiscal_year,
                    "period_end": p.period_end.isoformat(),
                    "currency": p.currency, "source": p.source, "items": items})
    return envelope({"period_type": period, "periods": out},
                    sources=sorted({p.source for p in periods[-limit:]}),
                    freshness={"latest_period": periods[-1].period_end.isoformat()})


@router.get("/{company_id}/dividends")
async def get_dividends(company_id: uuid.UUID, session=Depends(get_session)) -> dict:
    repo = ActionsRepository(session)
    divs = await repo.dividends(company_id)
    return envelope({
        "dividends": [{"ex_date": d.ex_date.isoformat(), "amount": str(d.amount),
                       "currency": d.currency} for d in divs]},
        sources=sorted({d.source for d in divs}))


@router.get("/{company_id}/splits")
async def get_splits(company_id: uuid.UUID, session=Depends(get_session)) -> dict:
    repo = ActionsRepository(session)
    splits = await repo.splits(company_id)
    return envelope({
        "splits": [{"ex_date": s.ex_date.isoformat(),
                    "ratio": f"{s.numerator}:{s.denominator}"} for s in splits]},
        sources=sorted({s.source for s in splits}))
