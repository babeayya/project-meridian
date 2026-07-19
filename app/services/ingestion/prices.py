"""Price ingestion: walk the OHLCV fallback chain, normalize, upsert, stamp
provenance. Quote refresh is best-effort (a failed quote never fails the run)."""
import uuid

import structlog

from app.core.errors import DataUnavailable, EntityNotFound
from app.providers.base import Capability, SymbolRef, region_for_exchange
from app.providers.registry import ProviderRegistry
from app.repositories.company import CompanyRepository
from app.repositories.prices import PriceRepository
from app.schemas.prices import RefreshResult

log = structlog.get_logger(__name__)

RANGE_DAYS = {"1m": 31, "3m": 93, "6m": 186, "1y": 366, "2y": 731,
              "5y": 1827, "10y": 3653, "max": 14600}


class PriceIngestionService:
    def __init__(self, companies: CompanyRepository, prices: PriceRepository,
                 registry: ProviderRegistry) -> None:
        self.companies = companies
        self.prices = prices
        self.registry = registry

    async def refresh(self, company_id: uuid.UUID,
                      range_: str = "5y") -> RefreshResult:
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            raise EntityNotFound(f"No listing for company {company_id}")

        ref = SymbolRef(
            ticker=listing.ticker,
            exchange=listing.exchange,
            yahoo_symbol=listing.yahoo_symbol,
            region=region_for_exchange(listing.exchange),
        )
        lookback = RANGE_DAYS.get(range_, RANGE_DAYS["5y"])

        bars, price_source = await self.registry.call(
            Capability.OHLCV_DAILY, ref.region, "daily_ohlcv",
            ref=ref, lookback_days=lookback,
        )
        upserted = await self.prices.upsert_daily(listing.id, bars, price_source)

        warnings: list[str] = []
        quote_source: str | None = None
        try:
            quote, quote_source = await self.registry.call(
                Capability.QUOTE, ref.region, "quote", ref=ref
            )
            await self.prices.upsert_quote(listing.id, quote, quote_source)
            if quote.currency and not listing.currency:
                listing.currency = quote.currency
        except DataUnavailable as exc:
            warnings.append(f"quote unavailable: {exc.detail}")
            log.warning("quote_refresh_failed", listing=listing.ticker)

        log.info("prices_refreshed", ticker=listing.ticker,
                 bars=upserted, source=price_source)
        return RefreshResult(
            company_id=company_id, listing_id=listing.id,
            bars_upserted=upserted, price_source=price_source,
            quote_source=quote_source, warnings=warnings,
        )
