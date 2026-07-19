import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.statements.history import FinancialHistory, PeriodFinancials
from app.models.fundamentals import FinancialLineItem, FinancialPeriod
from app.providers.base import StatementPeriodDTO


class FundamentalsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_periods(self, company_id: uuid.UUID, period_type: str,
                              periods: list[StatementPeriodDTO], source: str) -> int:
        """Idempotent refresh: replaces the given period_type set wholesale so a
        re-run from a better source never leaves stale mixed rows."""
        await self.session.execute(
            delete(FinancialPeriod).where(
                FinancialPeriod.company_id == company_id,
                FinancialPeriod.period_type == period_type,
            )
        )
        now = datetime.now(UTC)
        for p in periods:
            row = FinancialPeriod(
                company_id=company_id, period_type=period_type,
                fiscal_year=p.fiscal_year, period_end=p.period_end,
                currency=p.currency, source=source, source_url=p.source_url,
                fetched_at=now, raw=p.raw_fragment,
            )
            row.line_items = [
                FinancialLineItem(key=k, value=v) for k, v in p.items.items()
            ]
            self.session.add(row)
        await self.session.flush()
        return len(periods)

    async def history(self, company_id: uuid.UUID) -> FinancialHistory:
        stmt = (
            select(FinancialPeriod)
            .where(FinancialPeriod.company_id == company_id)
            .order_by(FinancialPeriod.period_end)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        annual, quarterly = [], []
        currency = "USD"
        for r in rows:
            pf = PeriodFinancials(
                fiscal_year=r.fiscal_year, period_end=r.period_end,
                period_type=r.period_type, currency=r.currency, source=r.source,
                items={li.key: li.value for li in r.line_items},
            )
            currency = r.currency
            (annual if r.period_type == "annual" else quarterly).append(pf)
        return FinancialHistory(annual=annual, quarterly=quarterly, currency=currency)

    async def has_annual(self, company_id: uuid.UUID) -> bool:
        stmt = select(FinancialPeriod.id).where(
            FinancialPeriod.company_id == company_id,
            FinancialPeriod.period_type == "annual",
        ).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None
