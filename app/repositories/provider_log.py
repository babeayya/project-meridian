from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.provider_log import ProviderCallLog


class ProviderLogRepository:
    """Writes call logs in a short-lived session of its own, so logging never
    entangles with (or rolls back with) business transactions.

    On SQLite (single-writer dev database) DB logging is disabled: the insert
    would contend with the open request transaction. structlog still records
    every provider call; Postgres gets the full audit table."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._factory = session_factory
        self._enabled: bool | None = None

    async def log(self, provider: str, method: str, ok: bool,
                  latency_ms: int, error: str | None) -> None:
        async with self._factory() as session:
            if self._enabled is None:
                self._enabled = session.get_bind().dialect.name != "sqlite"
            if not self._enabled:
                return
            session.add(ProviderCallLog(
                provider=provider, method=method, ok=ok,
                latency_ms=latency_ms, error=error,
            ))
            await session.commit()
