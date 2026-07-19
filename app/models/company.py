import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin


class Company(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str] = mapped_column(String(2), default="US")
    cik: Mapped[str | None] = mapped_column(String(10), unique=True)
    isin: Mapped[str | None] = mapped_column(String(12), unique=True)
    sector: Mapped[str | None] = mapped_column(String(120))
    industry: Mapped[str | None] = mapped_column(String(120))
    website: Mapped[str | None] = mapped_column(String(255))
    ir_url: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    reporting_currency: Mapped[str | None] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )
    aliases: Mapped[list["CompanyAlias"]] = relationship(
        back_populates="company", cascade="all, delete-orphan", lazy="selectin"
    )


class Listing(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("ticker", "exchange", name="uq_listing_ticker_exchange"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    ticker: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(32))
    yahoo_symbol: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str | None] = mapped_column(String(3))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    company: Mapped[Company] = relationship(back_populates="listings")


class CompanyAlias(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "company_aliases"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    alias: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str | None] = mapped_column(String(64))

    company: Mapped[Company] = relationship(back_populates="aliases")
