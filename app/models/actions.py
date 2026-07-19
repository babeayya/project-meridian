import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin


class Dividend(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "dividends"
    __table_args__ = (UniqueConstraint("company_id", "ex_date", "amount",
                                       name="uq_dividend"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    ex_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    source: Mapped[str] = mapped_column(String(32))


class StockSplit(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "stock_splits"
    __table_args__ = (UniqueConstraint("company_id", "ex_date", name="uq_split"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    ex_date: Mapped[date] = mapped_column(Date)
    numerator: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    denominator: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    source: Mapped[str] = mapped_column(String(32))
