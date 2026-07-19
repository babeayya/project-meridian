import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_company_repo, get_price_ingestion, get_price_repo
from app.core.errors import EntityNotFound
from app.repositories.company import CompanyRepository
from app.repositories.prices import PriceRepository
from app.schemas.common import envelope
from app.schemas.prices import PricePoint, PriceSeries, QuoteOut
from app.services.ingestion.prices import RANGE_DAYS, PriceIngestionService

router = APIRouter(prefix="/companies", tags=["prices"])


@router.get("/{company_id}/prices")
async def get_prices(
    company_id: uuid.UUID,
    companies: Annotated[CompanyRepository, Depends(get_company_repo)],
    prices: Annotated[PriceRepository, Depends(get_price_repo)],
    ingestion: Annotated[PriceIngestionService, Depends(get_price_ingestion)],
    range_: Annotated[str, Query(alias="range")] = "1y",
) -> dict:
    listing = await companies.primary_listing(company_id)
    if listing is None:
        raise EntityNotFound(f"Company {company_id} not found or has no listing")

    start = date.today() - timedelta(days=RANGE_DAYS.get(range_, 366))
    rows = await prices.series(listing.id, start=start)
    if not rows:
        # first request for this company: ingest through the chain, then serve
        await ingestion.refresh(company_id, range_ if range_ in RANGE_DAYS else "5y")
        rows = await prices.series(listing.id, start=start)

    series = PriceSeries(
        listing_id=listing.id, ticker=listing.ticker, exchange=listing.exchange,
        currency=listing.currency,
        points=[
            PricePoint(date=r.date, open=r.open, high=r.high, low=r.low,
                       close=r.close, adj_close=r.adj_close, volume=r.volume)
            for r in rows
        ],
    )
    sources = sorted({r.source for r in rows})
    freshness = {"latest_bar": rows[-1].date.isoformat() if rows else None,
                 "bars": len(rows)}
    return envelope(series.model_dump(mode="json"), sources=sources, freshness=freshness)


@router.get("/{company_id}/quote")
async def get_quote(
    company_id: uuid.UUID,
    companies: Annotated[CompanyRepository, Depends(get_company_repo)],
    prices: Annotated[PriceRepository, Depends(get_price_repo)],
    ingestion: Annotated[PriceIngestionService, Depends(get_price_ingestion)],
) -> dict:
    listing = await companies.primary_listing(company_id)
    if listing is None:
        raise EntityNotFound(f"Company {company_id} not found or has no listing")

    quote = await prices.get_quote(listing.id)
    if quote is None:
        await ingestion.refresh(company_id, "1m")
        quote = await prices.get_quote(listing.id)
    if quote is None:
        raise EntityNotFound("No quote available for this listing yet")

    out = QuoteOut(
        listing_id=listing.id, ticker=listing.ticker, price=quote.price,
        currency=quote.currency, change_pct=quote.change_pct,
        market_cap=quote.market_cap, as_of=quote.as_of, source=quote.source,
    )
    return envelope(out.model_dump(mode="json"), sources=[quote.source],
                    freshness={"as_of": quote.as_of.isoformat()})
