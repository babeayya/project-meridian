import uuid
from decimal import Decimal

from sqlalchemy import JSON, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin


class AssumptionSetRow(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "assumption_sets"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64), default="base")
    assumptions: Mapped[dict] = mapped_column(JSON)      # AssumptionSet schema dump
    derivation: Mapped[dict | None] = mapped_column(JSON)


class ValuationRun(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "valuation_runs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16))      # ok | not_applicable
    not_applicable_reason: Mapped[str | None] = mapped_column(Text)
    fair_value_per_share: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    price_at_run: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    upside_pct: Mapped[float | None] = mapped_column(Float)
    low: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    assumption_set_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assumption_sets.id", ondelete="SET NULL"))
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    trace: Mapped[dict | None] = mapped_column(JSON)
    engine_version: Mapped[str] = mapped_column(String(32), default="0.1.0")
