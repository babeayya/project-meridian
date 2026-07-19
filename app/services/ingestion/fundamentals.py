"""Fundamentals ingestion: statements (annual + quarterly), dividends, splits.
Walks the fallback chains, applies validation gates, stores with provenance."""
import uuid
from decimal import Decimal

import structlog
from pydantic import BaseModel

from app.core.errors import DataUnavailable, EntityNotFound
from app.providers.base import Capability, StatementPeriodDTO, SymbolRef, region_for_exchange
from app.providers.registry import ProviderRegistry
from app.repositories.actions import ActionsRepository
from app.repositories.company import CompanyRepository
from app.repositories.fundamentals import FundamentalsRepository

log = structlog.get_logger(__name__)


class FundamentalsRefreshResult(BaseModel):
    company_id: uuid.UUID
    annual_periods: int = 0
    quarterly_periods: int = 0
    dividends: int = 0
    splits: int = 0
    sources: dict[str, str] = {}
    warnings: list[str] = []


def validate_periods(
        periods: list[StatementPeriodDTO]) -> tuple[list[str], list[str]]:
    """Sanity gates. Hard problems reject the payload outright (the chain
    continues); soft problems (e.g. balance-sheet identity drift, often a
    provider's minority-interest presentation) reject only if a cleaner
    source exists — otherwise the payload is accepted WITH warnings."""
    hard: list[str] = []
    soft: list[str] = []
    if not periods:
        return ["empty period set"], []
    for p in periods:
        rev = p.items.get("revenue")
        ta = p.items.get("total_assets")
        if rev is not None and rev < 0:
            hard.append(f"{p.period_end}: negative revenue")
        if ta is not None and ta <= 0:
            hard.append(f"{p.period_end}: non-positive total assets")
        tl, eq = p.items.get("total_liabilities"), p.items.get("total_equity")
        mi = p.items.get("minority_interest") or Decimal(0)
        if None not in (ta, tl, eq) and ta:
            imbalance = abs((tl + eq + mi) - ta) / ta
            if imbalance > Decimal("0.15"):
                hard.append(f"{p.period_end}: balance sheet off by {imbalance:.1%}")
            elif imbalance > Decimal("0.05"):
                soft.append(f"{p.period_end}: balance sheet off by {imbalance:.1%}")
    ends = [p.period_end for p in periods]
    if ends != sorted(ends):
        hard.append("period dates not monotonic")
    return hard, soft


class FundamentalsIngestionService:
    def __init__(self, companies: CompanyRepository,
                 fundamentals: FundamentalsRepository,
                 actions: ActionsRepository,
                 registry: ProviderRegistry) -> None:
        self.companies = companies
        self.fundamentals = fundamentals
        self.actions = actions
        self.registry = registry

    async def _ref(self, company_id: uuid.UUID) -> SymbolRef:
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            raise EntityNotFound(f"No listing for company {company_id}")
        return SymbolRef(ticker=listing.ticker, exchange=listing.exchange,
                         yahoo_symbol=listing.yahoo_symbol,
                         region=region_for_exchange(listing.exchange))

    async def refresh(self, company_id: uuid.UUID) -> FundamentalsRefreshResult:
        ref = await self._ref(company_id)
        result = FundamentalsRefreshResult(company_id=company_id)
        company = await self.companies.get(company_id)

        for period_type, capability in [
            ("annual", Capability.STATEMENTS_ANNUAL),
            ("quarterly", Capability.STATEMENTS_QUARTERLY),
        ]:
            try:
                periods, source, soft_warnings = await self._fetch_validated(
                    capability, ref, period_type, company.cik if company else None)
                result.warnings.extend(
                    f"{period_type} ({source}, accepted with data-quality flags): {w}"
                    for w in soft_warnings[:4])
                n = await self.fundamentals.replace_periods(
                    company_id, period_type, periods, source)
                result.sources[period_type] = source
                if period_type == "annual":
                    result.annual_periods = n
                    if company and periods:
                        company.reporting_currency = periods[-1].currency
                else:
                    result.quarterly_periods = n
            except DataUnavailable as exc:
                result.warnings.append(f"{period_type} statements: {exc.detail}")

        currency = company.reporting_currency if company else None
        try:
            divs, source = await self.registry.call(
                Capability.DIVIDENDS, ref.region, "dividends",
                ref=ref, lookback_days=3660)
            result.dividends = await self.actions.replace_dividends(
                company_id, divs, source, currency)
            result.sources["dividends"] = source
        except DataUnavailable as exc:
            result.warnings.append(f"dividends: {exc.detail}")
        try:
            splits, source = await self.registry.call(
                Capability.SPLITS, ref.region, "splits", ref=ref, lookback_days=3660)
            result.splits = await self.actions.replace_splits(company_id, splits, source)
            result.sources["splits"] = source
        except DataUnavailable as exc:
            result.warnings.append(f"splits: {exc.detail}")

        log.info("fundamentals_refreshed", company_id=str(company_id),
                 annual=result.annual_periods, quarterly=result.quarterly_periods)
        return result

    async def _fetch_validated(
            self, capability: Capability, ref: SymbolRef,
            period_type: str, cik: str | None
    ) -> tuple[list[StatementPeriodDTO], str, list[str]]:
        """Walk the chain manually so validation-gate failures also fall
        through to the next provider. A payload with only soft problems is
        kept as a fallback and used if no cleaner source exists."""
        tried: list[str] = []
        fallback: tuple[list[StatementPeriodDTO], str, list[str]] | None = None
        for adapter in self.registry._eligible(capability, ref.region):
            skip = await self.registry._gate(adapter)
            if skip:
                tried.append(f"{adapter.name} ({skip})")
                continue
            try:
                periods = await self.registry._invoke(
                    adapter, "statements",
                    {"ref": ref, "period_type": period_type, "cik": cik})
            except Exception as exc:
                tried.append(f"{adapter.name} ({str(exc)[:120]})")
                continue
            hard, soft = validate_periods(periods)
            if hard:
                tried.append(f"{adapter.name} (validation: {hard[:2]})")
                log.warning("statements_rejected", provider=adapter.name,
                            problems=hard[:5])
                continue
            if soft:
                log.warning("statements_soft_flags", provider=adapter.name,
                            problems=soft[:5])
                # isolated flags (≤25% of periods, e.g. one old year's tag
                # artifact) don't forfeit a long history to a shorter source
                if len(soft) <= max(1, len(periods) // 4):
                    return periods, adapter.name, soft
                if fallback is None:
                    fallback = (periods, adapter.name, soft)
                tried.append(f"{adapter.name} (soft flags: {len(soft)})")
                continue
            return periods, adapter.name, []
        if fallback is not None:
            return fallback
        raise DataUnavailable(capability.value, tried)
