import difflib
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company, CompanyAlias, Listing


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, company_id: uuid.UUID) -> Company | None:
        return await self.session.get(Company, company_id)

    async def get_by_ticker(self, ticker: str, exchange: str) -> Listing | None:
        stmt = select(Listing).where(
            Listing.ticker == ticker.upper(), Listing.exchange == exchange.upper()
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def primary_listing(self, company_id: uuid.UUID) -> Listing | None:
        stmt = (
            select(Listing)
            .where(Listing.company_id == company_id)
            .order_by(Listing.is_primary.desc(), Listing.created_at)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def search_local(self, query: str, limit: int = 5) -> list[tuple[Company, float]]:
        """Substring match on name/alias/ticker, re-scored with string similarity.

        Portable across SQLite (dev/tests) and Postgres; a pg_trgm-backed
        version can replace the scan when the corpus grows (Phase 2+ seeds).
        """
        pattern = f"%{query}%"
        stmt = (
            select(Company)
            .outerjoin(Listing)
            .outerjoin(CompanyAlias)
            .where(or_(
                Company.name.ilike(pattern),
                Listing.ticker.ilike(query),
                CompanyAlias.alias.ilike(pattern),
            ))
            .distinct()
            .limit(50)
        )
        companies = (await self.session.execute(stmt)).scalars().all()
        scored = []
        for c in companies:
            best = _similarity(query, c.name)
            for listing in c.listings:
                if listing.ticker.lower() == query.lower():
                    best = max(best, 1.0)
            for alias in c.aliases:
                best = max(best, _similarity(query, alias.alias))
            scored.append((c, round(best, 4)))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:limit]

    async def create_with_listing(
        self, *, name: str, country: str, ticker: str, exchange: str,
        yahoo_symbol: str | None, currency: str | None,
    ) -> Company:
        existing = await self.get_by_ticker(ticker, exchange)
        if existing:
            return await self.session.get_one(Company, existing.company_id)
        company = Company(name=name, country=country, reporting_currency=currency)
        company.listings.append(Listing(
            ticker=ticker.upper(), exchange=exchange.upper(),
            yahoo_symbol=yahoo_symbol, currency=currency, is_primary=True,
        ))
        self.session.add(company)
        await self.session.flush()
        return company
