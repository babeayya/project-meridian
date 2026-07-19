"""Composition root: builds adapters, registry, and shared resources once at
startup; request-scoped repos/services are assembled in api/deps.py."""
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.control import ControlPlane, build_control_plane
from app.core.database import build_engine, build_session_factory
from app.core.http import HttpClient, build_http_client
from app.providers.alpha_vantage import AlphaVantageAdapter
from app.providers.base import ProviderAdapter
from app.providers.fmp import FmpAdapter
from app.providers.gdelt import GdeltAdapter, NewsApiAdapter
from app.providers.llm.openrouter import OpenRouterClient
from app.providers.registry import ProviderRegistry
from app.providers.sec_edgar import SecEdgarAdapter
from app.providers.stooq import StooqAdapter
from app.providers.yahoo import YahooAdapter
from app.providers.yahoo_fundamentals import YahooFundamentalsAdapter
from app.repositories.provider_log import ProviderLogRepository


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    http_raw: httpx.AsyncClient
    http: HttpClient
    control: ControlPlane
    registry: ProviderRegistry
    llm: OpenRouterClient | None = None

    async def aclose(self) -> None:
        await self.http_raw.aclose()
        await self.engine.dispose()


def build_adapters(settings: Settings, http: HttpClient) -> list[ProviderAdapter]:
    adapters: list[ProviderAdapter] = [
        YahooAdapter(http),
        StooqAdapter(http),
        YahooFundamentalsAdapter(http),
        SecEdgarAdapter(http, settings.sec_edgar_user_agent),
        GdeltAdapter(http),
    ]
    if settings.alpha_vantage_api_key:
        adapters.append(AlphaVantageAdapter(http, settings.alpha_vantage_api_key))
    if settings.fmp_api_key:
        adapters.append(FmpAdapter(http, settings.fmp_api_key))
    if settings.newsapi_api_key:
        adapters.append(NewsApiAdapter(http, settings.newsapi_api_key))
    return adapters


async def build_container(settings: Settings) -> Container:
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    http_raw = build_http_client(settings.http_connect_timeout, settings.http_read_timeout)
    http = HttpClient(http_raw)
    control = await build_control_plane(
        settings.redis_url,
        settings.circuit_failure_threshold,
        settings.circuit_cooldown_seconds,
    )
    call_logger = ProviderLogRepository(session_factory)
    registry = ProviderRegistry(
        build_adapters(settings, http), control, call_logger=call_logger.log
    )
    llm = (OpenRouterClient(http_raw, settings.openrouter_api_key,
                            settings.llm_model_analysis)
           if settings.openrouter_api_key else None)
    return Container(
        settings=settings, engine=engine, session_factory=session_factory,
        http_raw=http_raw, http=http, control=control, registry=registry,
        llm=llm,
    )
