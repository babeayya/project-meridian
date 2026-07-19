import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UuidPkMixin


class NewsArticle(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "news_articles"

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    outlet: Mapped[str | None] = mapped_column(String(200))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    language: Mapped[str | None] = mapped_column(String(8))
    provider: Mapped[str] = mapped_column(String(32))

    analysis: Mapped["NewsAnalysis | None"] = relationship(
        back_populates="article", uselist=False,
        cascade="all, delete-orphan", lazy="selectin")


class NewsAnalysis(Base, TimestampMixin):
    __tablename__ = "news_analysis"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"), primary_key=True)
    sentiment: Mapped[str] = mapped_column(String(12))       # positive|neutral|negative
    sentiment_score: Mapped[float] = mapped_column(Float)    # -1..1
    confidence: Mapped[float] = mapped_column(Float)
    importance: Mapped[float] = mapped_column(Float)         # 0..1
    category: Mapped[str | None] = mapped_column(String(32))
    expected_impact: Mapped[str | None] = mapped_column(Text)
    affected_segments: Mapped[list | None] = mapped_column(JSON)
    method: Mapped[str] = mapped_column(String(32))          # llm:<model> | lexicon
    prompt_version: Mapped[str | None] = mapped_column(String(16))

    article: Mapped[NewsArticle] = relationship(back_populates="analysis")
