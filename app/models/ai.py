import uuid

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UuidPkMixin


class AiAnalysis(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "ai_analyses"

    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)
    output: Mapped[dict] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16))
    input_refs: Mapped[dict | None] = mapped_column(JSON)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
