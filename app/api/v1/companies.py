import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_company_repo, get_price_ingestion, get_resolution_service
from app.core.errors import EntityNotFound
from app.repositories.company import CompanyRepository
from app.schemas.common import envelope
from app.schemas.company import CompanyProfile, ResolveCandidate, ResolveRequest
from app.services.ingestion.prices import PriceIngestionService
from app.services.resolution import ResolutionService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("/resolve")
async def resolve(
    body: ResolveRequest,
    service: Annotated[ResolutionService, Depends(get_resolution_service)],
) -> dict:
    result = await service.resolve(body.query)
    return envelope(result.model_dump(mode="json"))


@router.post("/resolve/select")
async def resolve_select(
    candidate: ResolveCandidate,
    service: Annotated[ResolutionService, Depends(get_resolution_service)],
) -> dict:
    """Persist a candidate the user picked from an ambiguous resolve."""
    profile = await service.select(candidate)
    return envelope(profile.model_dump(mode="json"))


@router.get("/{company_id}")
async def get_company(
    company_id: uuid.UUID,
    companies: Annotated[CompanyRepository, Depends(get_company_repo)],
) -> dict:
    company = await companies.get(company_id)
    if company is None:
        raise EntityNotFound(f"Company {company_id} not found")
    return envelope(CompanyProfile.model_validate(company).model_dump(mode="json"))


@router.post("/{company_id}/refresh")
async def refresh(
    company_id: uuid.UUID,
    ingestion: Annotated[PriceIngestionService, Depends(get_price_ingestion)],
    range_: Annotated[str, Query(alias="range")] = "5y",
) -> dict:
    """Refresh market data through the fallback chain (synchronous; the Celery
    task variant handles scheduled/bulk refreshes)."""
    result = await ingestion.refresh(company_id, range_)
    return envelope(result.model_dump(mode="json"),
                    sources=[result.price_source], warnings=result.warnings)
