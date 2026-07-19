"""News and AI-analysis endpoints."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_ai_service, get_news_service, get_session
from app.core.errors import EntityNotFound
from app.repositories.ai import AiRepository
from app.repositories.news import NewsRepository
from app.schemas.common import envelope
from app.services.ai_agents import AGENT_SCHEMAS, AiAgentService
from app.services.news_service import NewsService

router = APIRouter(prefix="/companies", tags=["news", "ai"])

NewsDep = Annotated[NewsService, Depends(get_news_service)]
AiDep = Annotated[AiAgentService, Depends(get_ai_service)]


@router.post("/{company_id}/news/refresh")
async def refresh_news(company_id: uuid.UUID, service: NewsDep,
                       lookback_days: Annotated[int, Query(ge=1, le=90)] = 30) -> dict:
    return envelope(await service.refresh(company_id, lookback_days))


@router.get("/{company_id}/news")
async def get_news(
    company_id: uuid.UUID,
    session=Depends(get_session),
    days: Annotated[int, Query(ge=1, le=365)] = 90,
    sentiment: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    repo = NewsRepository(session)
    articles = await repo.recent(company_id, days=days, sentiment=sentiment,
                                 limit=limit)
    return envelope({"articles": [
        {"id": str(a.id), "headline": a.headline, "url": a.url,
         "outlet": a.outlet, "provider": a.provider,
         "published_at": a.published_at.isoformat() if a.published_at else None,
         "analysis": {
             "sentiment": a.analysis.sentiment,
             "sentiment_score": a.analysis.sentiment_score,
             "confidence": a.analysis.confidence,
             "importance": a.analysis.importance,
             "category": a.analysis.category,
             "expected_impact": a.analysis.expected_impact,
             "method": a.analysis.method,
         } if a.analysis else None}
        for a in articles]})


@router.get("/{company_id}/news/sentiment-timeline")
async def sentiment_timeline(company_id: uuid.UUID, service: NewsDep,
                             days: Annotated[int, Query(ge=7, le=365)] = 90) -> dict:
    return envelope({"timeline": await service.sentiment_timeline(company_id, days)})


class AnalyzeRequest(BaseModel):
    agents: list[str] | None = None


@router.post("/{company_id}/ai/analyze")
async def ai_analyze(company_id: uuid.UUID, service: AiDep,
                     body: AnalyzeRequest | None = None) -> dict:
    body = body or AnalyzeRequest()
    return envelope(await service.run_all(company_id, body.agents))


@router.get("/{company_id}/ai/analyses")
async def ai_analyses(company_id: uuid.UUID, session=Depends(get_session),
                      agent: Annotated[str | None, Query()] = None) -> dict:
    repo = AiRepository(session)
    rows = await repo.latest(company_id, agent)
    if agent and not rows:
        raise EntityNotFound(f"No stored analysis for agent '{agent}' — "
                             f"POST /ai/analyze first")
    return envelope({"analyses": [
        {"agent": r.agent, "output": r.output, "model": r.model,
         "prompt_version": r.prompt_version, "confidence": r.confidence,
         "tokens": {"in": r.tokens_in, "out": r.tokens_out},
         "created_at": r.created_at.isoformat()} for r in rows],
        "available_agents": sorted(AGENT_SCHEMAS)})


@router.get("/{company_id}/ai/thesis")
async def ai_thesis(company_id: uuid.UUID, session=Depends(get_session)) -> dict:
    repo = AiRepository(session)
    rows = await repo.latest(company_id, "thesis")
    if not rows:
        raise EntityNotFound("No thesis yet — POST /ai/analyze first")
    r = rows[0]
    return envelope({"thesis": r.output, "model": r.model,
                     "created_at": r.created_at.isoformat()})
