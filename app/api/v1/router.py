from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.v1 import (
    analysis,
    charts,
    companies,
    financials,
    health,
    news_ai,
    prices,
    valuations,
)

api_router = APIRouter(prefix="/api/v1")

# health endpoints stay unauthenticated for probes
api_router.include_router(health.router)
for module in (companies, prices, financials, analysis, valuations, news_ai, charts):
    api_router.include_router(module.router, dependencies=[Depends(require_api_key)])
