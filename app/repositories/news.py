import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news import NewsAnalysis, NewsArticle


class NewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def existing_hashes(self, hashes: list[str]) -> set[str]:
        if not hashes:
            return set()
        stmt = select(NewsArticle.url_hash).where(NewsArticle.url_hash.in_(hashes))
        return set((await self.session.execute(stmt)).scalars().all())

    def add(self, article: NewsArticle) -> None:
        self.session.add(article)

    async def recent(self, company_id: uuid.UUID, days: int = 90,
                     sentiment: str | None = None,
                     limit: int = 100) -> list[NewsArticle]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = (select(NewsArticle)
                .where(NewsArticle.company_id == company_id,
                       NewsArticle.published_at >= cutoff)
                .order_by(NewsArticle.published_at.desc())
                .limit(limit))
        rows = list((await self.session.execute(stmt)).scalars().all())
        if sentiment:
            rows = [r for r in rows if r.analysis and r.analysis.sentiment == sentiment]
        return rows

    async def unanalyzed(self, company_id: uuid.UUID, limit: int = 50) -> list[NewsArticle]:
        stmt = (select(NewsArticle)
                .outerjoin(NewsAnalysis)
                .where(NewsArticle.company_id == company_id,
                       NewsAnalysis.article_id.is_(None))
                .limit(limit))
        return list((await self.session.execute(stmt)).scalars().all())
