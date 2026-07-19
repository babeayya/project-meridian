from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import Container
from app.core.errors import AuthFailed
from app.repositories.actions import ActionsRepository
from app.repositories.ai import AiRepository
from app.repositories.company import CompanyRepository
from app.repositories.fundamentals import FundamentalsRepository
from app.repositories.news import NewsRepository
from app.repositories.prices import PriceRepository
from app.repositories.valuation import ValuationRepository
from app.services.ai_agents import AiAgentService
from app.services.analysis import AnalysisService
from app.services.financials import FinancialsService
from app.services.ingestion.fundamentals import FundamentalsIngestionService
from app.services.ingestion.prices import PriceIngestionService
from app.services.macro import MacroService
from app.services.news_service import NewsService
from app.services.resolution import ResolutionService
from app.services.valuation_service import ValuationService


def get_container(request: Request) -> Container:
    return request.app.state.container


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_session(container: ContainerDep) -> AsyncIterator[AsyncSession]:
    async with container.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_api_key(
    container: ContainerDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    allowed = container.settings.api_key_list
    if not allowed:            # auth disabled (dev)
        return
    if x_api_key not in allowed:
        raise AuthFailed()


def get_company_repo(session: SessionDep) -> CompanyRepository:
    return CompanyRepository(session)


def get_price_repo(session: SessionDep) -> PriceRepository:
    return PriceRepository(session)


def get_resolution_service(
    container: ContainerDep,
    companies: Annotated[CompanyRepository, Depends(get_company_repo)],
) -> ResolutionService:
    return ResolutionService(companies, container.registry)


def get_price_ingestion(
    container: ContainerDep,
    companies: Annotated[CompanyRepository, Depends(get_company_repo)],
    prices: Annotated[PriceRepository, Depends(get_price_repo)],
) -> PriceIngestionService:
    return PriceIngestionService(companies, prices, container.registry)


def get_fundamentals_ingestion(
    container: ContainerDep, session: SessionDep,
) -> FundamentalsIngestionService:
    return FundamentalsIngestionService(
        CompanyRepository(session), FundamentalsRepository(session),
        ActionsRepository(session), container.registry)


def get_financials_service(session: SessionDep) -> FinancialsService:
    return FinancialsService(CompanyRepository(session),
                             FundamentalsRepository(session),
                             PriceRepository(session))


def get_macro_service(container: ContainerDep) -> MacroService:
    return MacroService(container.http, container.settings)


def get_analysis_service(
    session: SessionDep,
    financials: Annotated[FinancialsService, Depends(get_financials_service)],
    macro: Annotated[MacroService, Depends(get_macro_service)],
) -> AnalysisService:
    return AnalysisService(CompanyRepository(session), financials, macro)


def get_valuation_service(
    session: SessionDep,
    financials: Annotated[FinancialsService, Depends(get_financials_service)],
    macro: Annotated[MacroService, Depends(get_macro_service)],
) -> ValuationService:
    return ValuationService(CompanyRepository(session), financials,
                            ValuationRepository(session), macro)


def get_news_service(container: ContainerDep, session: SessionDep) -> NewsService:
    return NewsService(CompanyRepository(session), NewsRepository(session),
                       container.registry, container.llm,
                       container.settings.llm_model_classify)


def get_ai_service(
    container: ContainerDep, session: SessionDep,
    financials: Annotated[FinancialsService, Depends(get_financials_service)],
    analysis: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> AiAgentService:
    return AiAgentService(CompanyRepository(session), financials, analysis,
                          ValuationRepository(session), NewsRepository(session),
                          AiRepository(session), container.llm)
