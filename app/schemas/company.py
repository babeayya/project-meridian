import uuid

from pydantic import BaseModel, Field


class ResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=120)


class ListingOut(BaseModel):
    id: uuid.UUID
    ticker: str
    exchange: str
    yahoo_symbol: str | None
    currency: str | None
    is_primary: bool

    model_config = {"from_attributes": True}


class CompanyProfile(BaseModel):
    id: uuid.UUID
    name: str
    country: str
    sector: str | None
    industry: str | None
    website: str | None
    description: str | None
    reporting_currency: str | None
    listings: list[ListingOut]

    model_config = {"from_attributes": True}


class ResolveCandidate(BaseModel):
    company_id: uuid.UUID | None = None   # set when already persisted locally
    name: str
    ticker: str
    exchange: str
    symbol: str
    region: str
    confidence: float
    provider: str


class ResolveResponse(BaseModel):
    match: CompanyProfile | None = None   # confident single match (persisted)
    candidates: list[ResolveCandidate] = []
