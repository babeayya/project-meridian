"""Ratios, DuPont, scores, and quant — service-level assembly over the pure
domain engines."""
import uuid

from app.core.errors import EntityNotFound
from app.domain.quant import engine as quant
from app.domain.ratios.engine import all_ratios, dupont
from app.domain.scores import classic, factors
from app.domain.statements.classification import (
    is_financial,
    sector_hints_manufacturer,
)
from app.providers.base import Region, region_for_exchange
from app.repositories.company import CompanyRepository
from app.services.financials import FinancialsService
from app.services.macro import MacroService


class AnalysisService:
    def __init__(self, companies: CompanyRepository,
                 financials: FinancialsService, macro: MacroService) -> None:
        self.companies = companies
        self.financials = financials
        self.macro = macro

    async def ratios(self, company_id: uuid.UUID) -> dict:
        history = await self.financials.history(company_id)
        if history.latest is None:
            raise EntityNotFound("No fundamentals ingested — refresh first")
        market = await self.financials.market_inputs(company_id, history)
        groups = all_ratios(history.latest, history.prior, market)
        return {
            "as_of": history.latest.period_end.isoformat(),
            "currency": history.currency,
            "groups": {
                name: {k: n.to_dict() for k, n in group.items()}
                for name, group in groups.items()
            },
        }

    async def dupont(self, company_id: uuid.UUID, levels: int = 5) -> dict:
        history = await self.financials.history(company_id)
        node = dupont(history, levels)
        if node is None:
            raise EntityNotFound("Insufficient data for DuPont decomposition")
        return node.to_dict()

    def _company_flags(self, company, history) -> tuple[bool, bool]:
        """(is_financial, is_manufacturer) for Altman Z variant selection.

        Financial status is read from the financials themselves — sector and
        industry are never populated, so hint-matching alone always returned
        False and every filer got the general-purpose Z-score.
        """
        sector = getattr(company, "sector", None)
        industry = getattr(company, "industry", None)
        return (is_financial(history, sector, industry),
                sector_hints_manufacturer(sector, industry))

    async def scores(self, company_id: uuid.UUID) -> dict:
        company = await self.companies.get(company_id)
        if company is None:
            raise EntityNotFound(f"Company {company_id} not found")
        history = await self.financials.history(company_id)
        if history.latest is None:
            raise EntityNotFound("No fundamentals ingested — refresh first")
        market = await self.financials.market_inputs(company_id, history)
        is_fin, is_mfg = self._company_flags(company, history)

        altman = classic.altman_z(
            history.latest, market.market_cap if market else None, is_fin, is_mfg)
        piotroski = classic.piotroski_f(history.latest, history.prior)
        beneish = classic.beneish_m(history.latest, history.prior)

        stock = await self.financials.price_series(company_id, days=400)
        mom_stats = quant.momentum_stats(stock) if stock else {}
        perf = quant.performance(stock, None, 0.04) if stock else None

        pillars = [
            factors.quality(history),
            factors.growth(history),
            factors.profitability(history),
            factors.value(history, market),
            factors.momentum(mom_stats.get("return_6m"), mom_stats.get("return_12m"),
                             mom_stats.get("pct_off_52w_high")),
            factors.risk(history,
                         perf.annualized_volatility if perf else None,
                         perf.max_drawdown if perf else None,
                         altman.grade if altman else None),
        ]
        comp = factors.composite(pillars)
        return {
            "classic": {
                "altman_z": altman.model_dump() if altman else None,
                "piotroski_f": piotroski.model_dump() if piotroski else None,
                "beneish_m": beneish.model_dump() if beneish else None,
            },
            "factors": {p.pillar: p.model_dump() for p in pillars},
            "composite": comp.model_dump(),
        }

    async def _benchmark(self, company_id: uuid.UUID,
                         range_: str) -> tuple[quant.PriceSeries | None, Region]:
        listing = await self.companies.primary_listing(company_id)
        region = region_for_exchange(listing.exchange) if listing else Region.US
        try:
            raw = await self.macro.benchmark_series(region, range_)
            from datetime import UTC, datetime
            pairs = [(datetime.fromtimestamp(t, tz=UTC).date(), c)
                     for t, c in zip(raw["timestamps"], raw["closes"], strict=False)
                     if c is not None]
            return quant.PriceSeries(dates=[d for d, _ in pairs],
                                     closes=[c for _, c in pairs]), region
        except Exception:
            return None, region

    async def quant_performance(self, company_id: uuid.UUID,
                                window_days: int = 1096) -> dict:
        stock = await self.financials.price_series(company_id, days=window_days)
        if stock is None:
            raise EntityNotFound("No price history — refresh prices first")
        listing = await self.companies.primary_listing(company_id)
        region = region_for_exchange(listing.exchange) if listing else Region.US
        rf, rf_source = await self.macro.risk_free_rate(region)
        bench, _ = await self._benchmark(company_id, "5y")
        perf = quant.performance(stock, bench, float(rf))
        if perf is None:
            raise EntityNotFound("Insufficient price history (need ≥60 sessions)")
        return {"metrics": perf.model_dump(),
                "risk_free_rate": {"value": str(rf), "source": rf_source},
                "benchmark": self.macro.benchmark_symbol(region)}

    async def quant_risk(self, company_id: uuid.UUID,
                         window_days: int = 1096) -> dict:
        stock = await self.financials.price_series(company_id, days=window_days)
        if stock is None:
            raise EntityNotFound("No price history — refresh prices first")
        r = quant.risk(stock)
        if r is None:
            raise EntityNotFound("Insufficient price history (need ≥100 sessions)")
        return r.model_dump()

    async def quant_rolling(self, company_id: uuid.UUID,
                            window: int = 90) -> dict:
        stock = await self.financials.price_series(company_id, days=1096)
        if stock is None:
            raise EntityNotFound("No price history — refresh prices first")
        bench, region = await self._benchmark(company_id, "5y")
        rf, _ = await self.macro.risk_free_rate(region)
        return {
            "rolling_beta": quant.rolling_beta(stock, bench, window) if bench else [],
            "rolling_sharpe": quant.rolling_sharpe(stock, float(rf), window),
            "window_days": window,
        }
