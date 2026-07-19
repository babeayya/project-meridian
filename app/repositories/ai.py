import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AiAnalysis


class AiRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, row: AiAnalysis) -> None:
        self.session.add(row)

    async def latest(self, company_id: uuid.UUID,
                     agent: str | None = None) -> list[AiAnalysis]:
        stmt = (select(AiAnalysis)
                .where(AiAnalysis.company_id == company_id)
                .order_by(AiAnalysis.created_at.desc()))
        if agent:
            stmt = stmt.where(AiAnalysis.agent == agent)
        rows = (await self.session.execute(stmt)).scalars().all()
        seen: dict[str, AiAnalysis] = {}
        for r in rows:
            seen.setdefault(r.agent, r)
        return list(seen.values())
