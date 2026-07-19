import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin


class FinancialPeriod(Base, UuidPkMixin, TimestampMixin):
    """One fiscal period (annual or quarterly) holding all canonical line
    items across income/balance/cashflow (statement type derives from the
    taxonomy key). Raw provider payload retained for reproducibility."""
    __tablename__ = "financial_periods"
    __table_args__ = (
        UniqueConstraint("company_id", "period_type", "period_end",
                         name="uq_period_company_type_end"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    period_type: Mapped[str] = mapped_column(String(12))       # annual | quarterly
    fiscal_year: Mapped[int]
    period_end: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict | None] = mapped_column(JSON)

    line_items: Mapped[list["FinancialLineItem"]] = relationship(
        back_populates="period", cascade="all, delete-orphan", lazy="selectin")


class FinancialLineItem(Base):
    __tablename__ = "financial_line_items"

    period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("financial_periods.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 4))

    period: Mapped[FinancialPeriod] = relationship(back_populates="line_items")
