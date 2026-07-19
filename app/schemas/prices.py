import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PricePoint(BaseModel):
    date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal
    adj_close: Decimal | None
    volume: int | None


class PriceSeries(BaseModel):
    listing_id: uuid.UUID
    ticker: str
    exchange: str
    currency: str | None
    points: list[PricePoint]


class QuoteOut(BaseModel):
    listing_id: uuid.UUID
    ticker: str
    price: Decimal
    currency: str | None
    change_pct: Decimal | None
    market_cap: Decimal | None
    as_of: datetime
    source: str


class RefreshResult(BaseModel):
    company_id: uuid.UUID
    listing_id: uuid.UUID
    bars_upserted: int
    price_source: str
    quote_source: str | None
    warnings: list[str] = []
