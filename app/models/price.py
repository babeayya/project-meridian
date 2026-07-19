import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PriceDaily(Base):
    __tablename__ = "prices_daily"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    close: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    adj_close: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuoteLatest(Base):
    __tablename__ = "quotes_latest"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(32))
