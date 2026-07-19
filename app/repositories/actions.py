import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.actions import Dividend, StockSplit
from app.providers.base import DividendDTO, SplitDTO


class ActionsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_dividends(self, company_id: uuid.UUID,
                                dividends: list[DividendDTO], source: str,
                                currency: str | None) -> int:
        await self.session.execute(
            delete(Dividend).where(Dividend.company_id == company_id))
        for d in dividends:
            self.session.add(Dividend(company_id=company_id, ex_date=d.ex_date,
                                      amount=d.amount, currency=currency,
                                      source=source))
        await self.session.flush()
        return len(dividends)

    async def replace_splits(self, company_id: uuid.UUID,
                             splits: list[SplitDTO], source: str) -> int:
        await self.session.execute(
            delete(StockSplit).where(StockSplit.company_id == company_id))
        for s in splits:
            self.session.add(StockSplit(company_id=company_id, ex_date=s.ex_date,
                                        numerator=s.numerator,
                                        denominator=s.denominator, source=source))
        await self.session.flush()
        return len(splits)

    async def dividends(self, company_id: uuid.UUID) -> list[Dividend]:
        stmt = (select(Dividend).where(Dividend.company_id == company_id)
                .order_by(Dividend.ex_date))
        return list((await self.session.execute(stmt)).scalars().all())

    async def splits(self, company_id: uuid.UUID) -> list[StockSplit]:
        stmt = (select(StockSplit).where(StockSplit.company_id == company_id)
                .order_by(StockSplit.ex_date))
        return list((await self.session.execute(stmt)).scalars().all())
