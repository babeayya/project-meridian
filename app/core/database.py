"""Async SQLAlchemy engine/session factory."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    kwargs: dict = {"echo": echo, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # single-writer engine: brief lock grace for overlapping requests
        kwargs["connect_args"] = {"timeout": 5}
    return create_async_engine(database_url, **kwargs)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create tables that don't exist yet. Alembic owns migrations in prod;
    this keeps dev/test bootstrapping zero-step."""
    import app.models  # noqa: F401  ensure all models are registered
    from app.models.base import Base  # local import: avoid import cycles

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
