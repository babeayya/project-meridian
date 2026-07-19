import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.price import PriceDaily, QuoteLatest
from app.providers.base import OhlcvBar, QuoteDTO

_UPSERT_COLS = ("open", "high", "low", "close", "adj_close", "volume",
                "source", "fetched_at")


def _insert_for(session: AsyncSession):
    """Dialect-appropriate INSERT with upsert support (postgres | sqlite)."""
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_daily(self, listing_id: uuid.UUID, bars: list[OhlcvBar],
                           source: str) -> int:
        if not bars:
            return 0
        now = datetime.now(UTC)
        insert = _insert_for(self.session)
        rows = [
            {
                "listing_id": listing_id, "date": b.date,
                "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                "adj_close": b.adj_close, "volume": b.volume,
                "source": source, "fetched_at": now,
            }
            for b in bars
        ]
        stmt = insert(PriceDaily)
        stmt = stmt.on_conflict_do_update(
            index_elements=["listing_id", "date"],
            set_={c: getattr(stmt.excluded, c) for c in _UPSERT_COLS},
        )
        await self.session.execute(stmt, rows)
        return len(rows)

    async def series(self, listing_id: uuid.UUID, start: date | None = None,
                     end: date | None = None) -> list[PriceDaily]:
        stmt = select(PriceDaily).where(PriceDaily.listing_id == listing_id)
        if start:
            stmt = stmt.where(PriceDaily.date >= start)
        if end:
            stmt = stmt.where(PriceDaily.date <= end)
        stmt = stmt.order_by(PriceDaily.date)
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest_date(self, listing_id: uuid.UUID) -> date | None:
        stmt = (
            select(PriceDaily.date)
            .where(PriceDaily.listing_id == listing_id)
            .order_by(PriceDaily.date.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_quote(self, listing_id: uuid.UUID, quote: QuoteDTO,
                           source: str) -> None:
        existing = await self.session.get(QuoteLatest, listing_id)
        if existing:
            existing.price = quote.price
            existing.currency = quote.currency
            existing.change_pct = quote.change_pct
            existing.market_cap = quote.market_cap
            existing.as_of = quote.as_of
            existing.source = source
        else:
            self.session.add(QuoteLatest(
                listing_id=listing_id, price=quote.price, currency=quote.currency,
                change_pct=quote.change_pct, market_cap=quote.market_cap,
                as_of=quote.as_of, source=source,
            ))

    async def get_quote(self, listing_id: uuid.UUID) -> QuoteLatest | None:
        return await self.session.get(QuoteLatest, listing_id)
