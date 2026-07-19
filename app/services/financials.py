"""Assembles domain inputs: financial history, market inputs, price series."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.core.errors import EntityNotFound
from app.domain.quant.engine import PriceSeries
from app.domain.ratios.engine import MarketInputs
from app.domain.statements.history import FinancialHistory
from app.domain.valuation.relative import YearEndPrice
from app.repositories.company import CompanyRepository
from app.repositories.fundamentals import FundamentalsRepository
from app.repositories.prices import PriceRepository


class FinancialsService:
    def __init__(self, companies: CompanyRepository,
                 fundamentals: FundamentalsRepository,
                 prices: PriceRepository) -> None:
        self.companies = companies
        self.fundamentals = fundamentals
        self.prices = prices

    async def history(self, company_id: uuid.UUID) -> FinancialHistory:
        company = await self.companies.get(company_id)
        if company is None:
            raise EntityNotFound(f"Company {company_id} not found")
        h = await self.fundamentals.history(company_id)
        h.company_name = company.name
        return h

    async def market_inputs(self, company_id: uuid.UUID,
                            history: FinancialHistory) -> MarketInputs | None:
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            return None
        quote = await self.prices.get_quote(listing.id)
        shares = history.latest_value("shares_diluted")
        if quote is None or shares is None or shares <= 0:
            return None
        return MarketInputs(price=quote.price, shares=shares,
                            market_cap=quote.price * shares)

    async def price(self, company_id: uuid.UUID) -> Decimal | None:
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            return None
        quote = await self.prices.get_quote(listing.id)
        return quote.price if quote else None

    async def price_series(self, company_id: uuid.UUID,
                           days: int = 1830) -> PriceSeries | None:
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            return None
        rows = await self.prices.series(
            listing.id, start=date.today() - timedelta(days=days))
        if not rows:
            return None
        return PriceSeries(
            dates=[r.date for r in rows],
            closes=[float(r.adj_close if r.adj_close is not None else r.close)
                    for r in rows],
        )

    async def year_end_prices(self, company_id: uuid.UUID,
                              history: FinancialHistory) -> list[YearEndPrice]:
        """Close nearest to (≤) each fiscal period end, for historical multiples."""
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            return []
        out: list[YearEndPrice] = []
        for p in history.annual:
            rows = await self.prices.series(
                listing.id, start=p.period_end - timedelta(days=10), end=p.period_end)
            if rows:
                out.append(YearEndPrice(fiscal_year=p.fiscal_year,
                                        price=rows[-1].close))
        return out
