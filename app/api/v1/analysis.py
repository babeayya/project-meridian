"""Ratios, DuPont, scores, and quant endpoints."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_analysis_service
from app.schemas.common import envelope
from app.services.analysis import AnalysisService

router = APIRouter(prefix="/companies", tags=["analysis"])

AnalysisDep = Annotated[AnalysisService, Depends(get_analysis_service)]

WINDOWS = {"1y": 366, "2y": 731, "3y": 1096, "5y": 1827}


@router.get("/{company_id}/ratios")
async def ratios(company_id: uuid.UUID, service: AnalysisDep) -> dict:
    return envelope(await service.ratios(company_id))


@router.get("/{company_id}/ratios/dupont")
async def dupont(company_id: uuid.UUID, service: AnalysisDep,
                 levels: Annotated[int, Query(ge=3, le=5)] = 5) -> dict:
    return envelope(await service.dupont(company_id, 3 if levels == 3 else 5))


@router.get("/{company_id}/scores")
async def scores(company_id: uuid.UUID, service: AnalysisDep) -> dict:
    return envelope(await service.scores(company_id))


@router.get("/{company_id}/quant/performance")
async def quant_performance(company_id: uuid.UUID, service: AnalysisDep,
                            window: Annotated[str, Query()] = "3y") -> dict:
    return envelope(await service.quant_performance(
        company_id, WINDOWS.get(window, 1096)))


@router.get("/{company_id}/quant/risk")
async def quant_risk(company_id: uuid.UUID, service: AnalysisDep,
                     window: Annotated[str, Query()] = "3y") -> dict:
    return envelope(await service.quant_risk(company_id, WINDOWS.get(window, 1096)))


@router.get("/{company_id}/quant/rolling")
async def quant_rolling(company_id: uuid.UUID, service: AnalysisDep,
                        window_days: Annotated[int, Query(ge=30, le=252)] = 90) -> dict:
    return envelope(await service.quant_rolling(company_id, window_days))
