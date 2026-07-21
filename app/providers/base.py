"""Provider adapter contract and normalized DTOs."""
from __future__ import annotations

from abc import ABC
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel

from app.core.control import RateLimit
from app.core.http import HttpClient


class Capability(StrEnum):
    SYMBOL_SEARCH = "symbol_search"
    QUOTE = "quote"
    OHLCV_DAILY = "ohlcv_daily"
    STATEMENTS_ANNUAL = "statements_annual"
    STATEMENTS_QUARTERLY = "statements_quarterly"
    BETA = "beta"
    DIVIDENDS = "dividends"
    SPLITS = "splits"
    NEWS = "news"


class Region(StrEnum):
    US = "US"
    IN = "IN"
    GLOBAL = "GLOBAL"


class ProviderError(Exception):
    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider


class NotSupported(ProviderError):
    """Adapter cannot serve this symbol/capability — chain moves on silently."""


class SymbolRef(BaseModel):
    """Provider-agnostic reference to a listed security; each adapter maps it
    to its own symbology."""
    ticker: str
    exchange: str                      # normalized: NASDAQ, NYSE, NSE, BSE, ...
    yahoo_symbol: str | None = None    # e.g. RELIANCE.NS
    region: Region = Region.US


class SymbolCandidate(BaseModel):
    symbol: str                        # provider-native symbol (yahoo style kept)
    ticker: str                        # bare ticker
    name: str
    exchange: str
    region: Region
    currency: str | None = None
    quote_type: str = "EQUITY"
    provider: str
    score: float = 0.0


class OhlcvBar(BaseModel):
    date: date
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal
    adj_close: Decimal | None = None
    volume: int | None = None


class QuoteDTO(BaseModel):
    price: Decimal
    currency: str | None = None
    change_pct: Decimal | None = None
    market_cap: Decimal | None = None
    as_of: datetime


class StatementPeriodDTO(BaseModel):
    """One normalized fiscal period: canonical taxonomy keys → values."""
    fiscal_year: int
    period_end: date
    period_type: str                    # 'annual' | 'quarterly'
    currency: str = "USD"
    items: dict[str, Decimal]
    source_url: str | None = None
    raw_fragment: dict | None = None


class DividendDTO(BaseModel):
    ex_date: date
    amount: Decimal


class SplitDTO(BaseModel):
    ex_date: date
    numerator: Decimal
    denominator: Decimal


class NewsItemDTO(BaseModel):
    url: str
    headline: str
    summary: str | None = None
    outlet: str | None = None
    published_at: datetime | None = None
    language: str | None = None


class ProviderAdapter(ABC):
    name: ClassVar[str]
    capabilities: ClassVar[frozenset[Capability]]
    regions: ClassVar[frozenset[Region]]
    rate_limit: ClassVar[RateLimit]

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    def supports(self, capability: Capability, region: Region) -> bool:
        if capability not in self.capabilities:
            return False
        return Region.GLOBAL in self.regions or region in self.regions

    # Capability methods — adapters override the ones they declare.
    async def search(self, query: str) -> list[SymbolCandidate]:
        raise NotSupported(self.name, "symbol_search not supported")

    async def daily_ohlcv(self, ref: SymbolRef, lookback_days: int) -> list[OhlcvBar]:
        raise NotSupported(self.name, "ohlcv_daily not supported")

    async def quote(self, ref: SymbolRef) -> QuoteDTO:
        raise NotSupported(self.name, "quote not supported")

    async def statements(self, ref: SymbolRef, period_type: str,
                         cik: str | None = None) -> list[StatementPeriodDTO]:
        raise NotSupported(self.name, "statements not supported")

    async def dividends(self, ref: SymbolRef, lookback_days: int) -> list[DividendDTO]:
        raise NotSupported(self.name, "dividends not supported")

    async def splits(self, ref: SymbolRef, lookback_days: int) -> list[SplitDTO]:
        raise NotSupported(self.name, "splits not supported")

    async def news(self, query: str, company_name: str,
                   lookback_days: int) -> list[NewsItemDTO]:
        raise NotSupported(self.name, "news not supported")


# Normalized exchange codes → region
EXCHANGE_REGION: dict[str, Region] = {
    "NASDAQ": Region.US, "NYSE": Region.US, "NYSEARCA": Region.US, "AMEX": Region.US,
    "BATS": Region.US, "OTC": Region.US,
    "NSE": Region.IN, "BSE": Region.IN,
}


def region_for_exchange(exchange: str) -> Region:
    return EXCHANGE_REGION.get(exchange.upper(), Region.GLOBAL)
