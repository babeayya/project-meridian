"""Celery ingestion tasks. Each task builds a short-lived runtime (engine +
providers), runs the async service, and tears down cleanly — workers never
share event loops across tasks."""
import asyncio
import uuid

from app.core.config import get_settings
from app.core.container import build_container
from app.repositories.company import CompanyRepository
from app.repositories.prices import PriceRepository
from app.services.ingestion.prices import PriceIngestionService
from app.workers.celery_app import celery_app


async def _refresh_prices(company_id: str, range_: str) -> dict:
    container = await build_container(get_settings())
    try:
        async with container.session_factory() as session:
            service = PriceIngestionService(
                CompanyRepository(session), PriceRepository(session),
                container.registry,
            )
            result = await service.refresh(uuid.UUID(company_id), range_)
            await session.commit()
            return result.model_dump(mode="json")
    finally:
        await container.aclose()


@celery_app.task(name="app.workers.tasks.ingestion.refresh_prices",
                 max_retries=2, default_retry_delay=60)
def refresh_prices(company_id: str, range_: str = "5y") -> dict:
    return asyncio.run(_refresh_prices(company_id, range_))
