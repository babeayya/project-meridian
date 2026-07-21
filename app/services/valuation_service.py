"""Valuation orchestration: derive default assumptions from ingested history +
live macro, apply user overrides, run models, persist runs with full traces."""
import uuid
from decimal import Decimal

import structlog

from app.core.errors import AppError, EntityNotFound
from app.domain.statements.classification import is_financial
from app.domain.statements.history import FinancialHistory
from app.domain.valuation.advanced import (
    expected_return,
    monte_carlo_dcf,
    reverse_dcf,
    scenarios,
    sensitivity,
    summarize,
)
from app.domain.valuation.base import AssumptionSet, ValuationOutcome, WaccInputs
from app.domain.valuation.dcf import dcf_fcfe, dcf_fcff
from app.domain.valuation.equity_models import asset_based, ddm, eva, residual_income
from app.domain.valuation.relative import historical_multiples
from app.providers.base import Capability, Region, SymbolRef, region_for_exchange
from app.providers.registry import ProviderRegistry
from app.repositories.company import CompanyRepository
from app.repositories.valuation import ValuationRepository
from app.services.financials import FinancialsService
from app.services.macro import MacroService

log = structlog.get_logger(__name__)

ENGINE_VERSION = "0.2.0"
ONE = Decimal(1)

# Every model that values the firm by discounting enterprise cash flows —
# directly, or by simulating/solving the same forecast. For a bank the split
# between operating and financing cash flow is arbitrary and "net debt" has no
# meaning, so all of these rest on an assumption that does not hold. They are
# de-weighted rather than suppressed: dropping them would silently transfer the
# whole blend onto the remaining models, which are no better calibrated here.
ENTERPRISE_MODELS = frozenset({
    "dcf_fcff", "eva", "scenario", "monte_carlo_dcf", "reverse_dcf",
    "expected_return",
})
ENTERPRISE_ON_FINANCIAL_WARNING = (
    "enterprise cash-flow framework is unreliable for financials — "
    "operating and financing flows are not separable, and net debt is not "
    "meaningful; prefer ddm / residual_income"
)
FINANCIAL_CONFIDENCE_FACTOR = 0.5

# Providers occasionally publish a placeholder or a stale outlier. Equity betas
# outside this band are not credible for a listed operating company, so they are
# rejected rather than propagated into WACC.
BETA_SANITY_MIN = Decimal("0.1")
BETA_SANITY_MAX = Decimal("4.0")


class ValuationService:
    def __init__(self, companies: CompanyRepository,
                 financials: FinancialsService,
                 valuations: ValuationRepository,
                 macro: MacroService,
                 registry: ProviderRegistry) -> None:
        self.companies = companies
        self.financials = financials
        self.valuations = valuations
        self.macro = macro
        self.registry = registry

    # ---------- default assumptions ----------

    async def build_default_assumptions(
            self, company_id: uuid.UUID) -> tuple[AssumptionSet, dict[str, str]]:
        history = await self.financials.history(company_id)
        latest = history.latest
        if latest is None:
            raise EntityNotFound(
                "No fundamentals ingested — call POST /companies/{id}/fundamentals/refresh first")
        listing = await self.companies.primary_listing(company_id)
        region = region_for_exchange(listing.exchange) if listing else Region.US
        derivation: dict[str, str] = {}

        hist_g3 = history.cagr("revenue", 3)
        hist_g5 = history.cagr("revenue", 5)
        base_g = hist_g3 if hist_g3 is not None else hist_g5
        if base_g is None:
            base_g = Decimal("0.04")
            derivation["revenue_growth"] = "no usable revenue history — default 4%"
        else:
            base_g = min(max(base_g, Decimal("-0.05")), Decimal("0.30"))
            derivation["revenue_growth"] = (
                f"3y CAGR {hist_g3} / 5y CAGR {hist_g5}, clamped to [−5%, 30%], "
                "fading linearly to terminal growth")
        terminal_g = Decimal("0.025") if region != Region.IN else Decimal("0.05")
        derivation["terminal_growth"] = (
            f"long-run nominal GDP proxy for {region.value}")
        years = 5
        growth_path = [
            (base_g + (terminal_g - base_g) * Decimal(i) / Decimal(years))
            .quantize(Decimal("0.0001"))
            for i in range(years)
        ]

        rev_by_fy = {fy: v for fy, v in history.series("revenue") if v}
        company = await self.companies.get(company_id)
        lender = is_financial(history, getattr(company, "sector", None),
                              getattr(company, "industry", None))
        ebit_by_fy, ebit_basis = self._ebit_series(history, lender)
        margins = [(fy, ebit / rev_by_fy[fy]) for fy, ebit in ebit_by_fy
                   if fy in rev_by_fy]
        if margins:
            recent = [m for _, m in margins[-3:]]
            base_margin = (sum(recent) / len(recent)).quantize(Decimal("0.0001"))
            derivation["ebit_margin"] = f"3y average {ebit_basis} margin {base_margin}"
        else:
            base_margin = Decimal("0.12")
            derivation["ebit_margin"] = "no margin history — default 12%"
        margin_path = [base_margin] * years

        def pct_of_revenue(key: str, default: Decimal, label: str) -> Decimal:
            pts = [v / rev_by_fy[fy] for fy, v in history.series(key)
                   if fy in rev_by_fy]
            if pts:
                val = (sum(pts[-3:]) / len(pts[-3:])).quantize(Decimal("0.0001"))
                derivation[label] = f"3y average {key}/revenue = {val}"
                return val
            derivation[label] = f"no history — default {default}"
            return default

        da_pct = pct_of_revenue("depreciation_amortization", Decimal("0.04"), "da_pct_revenue")
        capex_pct = pct_of_revenue("capex", Decimal("0.05"), "capex_pct_revenue")

        from app.domain.statements.derived import effective_tax_rate, net_debt
        tax_node = effective_tax_rate(latest)
        tax = tax_node.result if tax_node else Decimal("0.23")
        derivation["tax_rate"] = (tax_node.substitution if tax_node
                                  else "no tax history — default 23%")

        nd_node = net_debt(latest)
        nd = nd_node.result if nd_node else Decimal(0)
        derivation["net_debt"] = (nd_node.substitution if nd_node
                                  else "debt/cash data missing — assumed 0")

        shares = history.latest_value("shares_diluted") or Decimal(0)
        derivation["shares_diluted"] = (
            f"most recent reported diluted shares: {shares}"
            + ("" if latest.get("shares_diluted") is not None
               else " (latest period not yet reported — prior year used)"))

        rf, rf_source = await self.macro.risk_free_rate(region)
        derivation["risk_free_rate"] = f"{rf} from {rf_source}"
        beta, beta_source = await self._beta(company_id, region)
        derivation["beta"] = f"{beta} from {beta_source}"

        price = await self.financials.price(company_id)
        market_cap = (price * shares) if price and shares else Decimal(0)
        interest = latest.get("interest_expense")
        total_debt = latest.total_debt or Decimal(0)
        kd = None
        if interest and total_debt > 0:
            kd = (interest / total_debt).quantize(Decimal("0.0001"))
            kd = min(max(kd, Decimal("0.01")), Decimal("0.15"))
            derivation["cost_of_debt"] = f"interest {interest} / total debt {total_debt} = {kd}"

        erp = Decimal("0.05") if region != Region.IN else Decimal("0.065")
        derivation["equity_risk_premium"] = (
            f"{erp} — mature-market 5% (+150bp India country premium)"
            if region == Region.IN else f"{erp} — mature-market baseline")

        wacc_inputs = WaccInputs(risk_free_rate=rf, beta=beta,
                                 equity_risk_premium=erp, cost_of_debt=kd,
                                 tax_rate=tax, market_cap=market_cap,
                                 total_debt=total_debt, rf_source=rf_source,
                                 beta_source=beta_source)
        assumptions = AssumptionSet(
            forecast_years=years, revenue_growth=growth_path,
            ebit_margin=margin_path, tax_rate=tax, da_pct_revenue=da_pct,
            capex_pct_revenue=capex_pct,
            nwc_pct_revenue_delta=Decimal("0.02"),
            terminal_growth=terminal_g, shares_diluted=shares, net_debt=nd,
            minority_interest=latest.get("minority_interest") or Decimal(0),
            wacc=wacc_inputs,
            derivation=derivation,
        )
        derivation["nwc_pct_revenue_delta"] = "default 2% of incremental revenue"

        from app.domain.valuation.wacc import wacc as wacc_calc
        wacc_node = wacc_calc(wacc_inputs)
        derivation["wacc"] = f"{wacc_node.result} — {wacc_node.explanation}"
        derivation["forecast_horizon"] = (
            f"{years}y explicit forecast (revenue growth fades from {base_g:.1%} "
            f"toward the {terminal_g:.1%} terminal rate); Gordon-growth terminal "
            f"value applied from year {years + 1} onward")
        return assumptions, derivation

    @staticmethod
    def _ebit_series(history: FinancialHistory,
                     lender: bool) -> tuple[list[tuple[int, Decimal]], str]:
        """EBIT per fiscal year, with a reconstruction for filers that report no
        operating-income line. Banks and insurers (JPM, BAC, …) never tag
        us-gaap:OperatingIncomeLoss, which used to leave the margin history
        empty and drop the model onto its 12% placeholder.

        For a lender, interest is a cost of revenue rather than a financing
        charge, so it must not be added back — that would print a ~90% margin
        for JPM. `lender` is expected to come from
        `statements.classification.is_financial`, which reads the structure of
        the financials rather than trusting sector metadata.

        Returns (series, basis label) — the label is surfaced in the derivation
        so the trace never passes a proxy off as a reported EBIT.
        """
        reported = history.series("operating_income")
        if reported:
            return reported, "EBIT"

        pretax = history.series("pretax_income")
        if not pretax:
            return [], "EBIT"
        if lender:
            return pretax, "pre-tax (no operating-income line filed)"

        interest = dict(history.series("interest_expense"))
        return ([(fy, v + interest.get(fy, Decimal(0))) for fy, v in pretax],
                "EBIT (pre-tax + interest expense)")

    async def _beta(self, company_id: uuid.UUID, region: Region) -> tuple[Decimal, str]:
        """Beta as published by the data providers, not regressed here.

        Fitting our own left the terminal disagreeing with every screen the
        user could check it against, and the fit was fragile: a throttled
        benchmark response collapsed the overlap and produced 0.23 for JPM
        against a published 0.98. The provider chain (Yahoo → FMP) is the
        source of record; the rolling/CAPM regressions in the quant tab remain
        as analytics, clearly labelled as our own.
        """
        listing = await self.companies.primary_listing(company_id)
        if listing is None:
            return Decimal("1.0"), "assumption:default (no listing)"
        ref = SymbolRef(ticker=listing.ticker, exchange=listing.exchange,
                        yahoo_symbol=listing.yahoo_symbol, region=region)
        try:
            beta, source = await self.registry.call(
                Capability.BETA, region, "beta", ref=ref)
        except Exception as exc:
            log.warning("beta_lookup_failed", company_id=str(company_id),
                        error=str(exc)[:200])
            return Decimal("1.0"), "assumption:default (no published beta available)"
        if not (BETA_SANITY_MIN <= beta <= BETA_SANITY_MAX):
            log.warning("beta_out_of_range", company_id=str(company_id),
                        beta=str(beta), source=source)
            return (Decimal("1.0"),
                    f"assumption:default ({source} published {beta}, outside "
                    f"[{BETA_SANITY_MIN}, {BETA_SANITY_MAX}])")
        return beta, f"published:{source}"

    # ---------- model execution ----------

    async def _load_assumptions(self, company_id: uuid.UUID,
                                assumption_set_id: uuid.UUID | None,
                                overrides: dict | None) -> tuple[AssumptionSet, uuid.UUID | None]:
        if assumption_set_id:
            row = await self.valuations.get_assumptions(assumption_set_id)
            if row is None:
                raise EntityNotFound(f"Assumption set {assumption_set_id} not found")
            a = AssumptionSet.model_validate(row.assumptions)
            set_id = row.id
        else:
            a, derivation = await self.build_default_assumptions(company_id)
            row = await self.valuations.save_assumptions(
                company_id, "auto", a.model_dump(mode="json"), derivation)
            set_id = row.id
        if overrides:
            merged = a.model_dump()
            merged.update({k: v for k, v in overrides.items() if k in merged})
            a = AssumptionSet.model_validate(merged)
        return a, set_id

    async def run_model(self, company_id: uuid.UUID, model: str,
                        assumption_set_id: uuid.UUID | None = None,
                        overrides: dict | None = None) -> tuple[ValuationOutcome, uuid.UUID]:
        history = await self.financials.history(company_id)
        price = await self.financials.price(company_id)
        a, set_id = await self._load_assumptions(company_id, assumption_set_id, overrides)
        company = await self.companies.get(company_id)
        outcome = await self._dispatch(model, history, a, price, company_id)

        if model in ENTERPRISE_MODELS and is_financial(
                history, getattr(company, "sector", None),
                getattr(company, "industry", None)):
            outcome.caveat(ENTERPRISE_ON_FINANCIAL_WARNING,
                           FINANCIAL_CONFIDENCE_FACTOR)

        run = await self.valuations.save_run(company_id, outcome, price, set_id,
                                             ENGINE_VERSION)
        outcome.outputs["run_id"] = str(run.id)
        return outcome, run.id

    async def _dispatch(self, model: str, history: FinancialHistory,
                        a: AssumptionSet, price: Decimal | None,
                        company_id: uuid.UUID) -> ValuationOutcome:
        if model == "dcf_fcff":
            return dcf_fcff(history, a, price)
        if model == "dcf_fcfe":
            return dcf_fcfe(history, a, price)
        if model == "ddm":
            return ddm(history, a, price)
        if model == "residual_income":
            return residual_income(history, a, price)
        if model == "eva":
            return eva(history, a, price)
        if model == "asset_based":
            return asset_based(history, a, price)
        if model == "multiples":
            yep = await self.financials.year_end_prices(company_id, history)
            return historical_multiples(history, a, price, yep)
        if model == "reverse_dcf":
            return reverse_dcf(history, a, price)
        if model == "monte_carlo_dcf":
            return monte_carlo_dcf(history, a, price)
        if model == "scenario":
            return scenarios(history, a, price)
        if model == "expected_return":
            base = dcf_fcff(history, a, price)
            return expected_return(history, a, price, base.fair_value_per_share)
        raise AppError(f"Unknown valuation model '{model}'")

    ALL_MODELS = ["dcf_fcff", "dcf_fcfe", "ddm", "residual_income", "eva",
                  "asset_based", "multiples", "scenario", "monte_carlo_dcf",
                  "reverse_dcf", "expected_return"]

    async def run_all(self, company_id: uuid.UUID) -> dict:
        # derive defaults once (macro + beta fetches) and share across models
        a, derivation = await self.build_default_assumptions(company_id)
        row = await self.valuations.save_assumptions(
            company_id, "auto", a.model_dump(mode="json"), derivation)
        outcomes = []
        for model in self.ALL_MODELS:
            outcome, _ = await self.run_model(company_id, model,
                                              assumption_set_id=row.id)
            outcomes.append(outcome)
        price = await self.financials.price(company_id)
        return summarize(outcomes, price)

    async def sensitivity_grid(self, company_id: uuid.UUID,
                               assumption_set_id: uuid.UUID | None = None,
                               steps: int = 5) -> dict:
        history = await self.financials.history(company_id)
        a, _ = await self._load_assumptions(company_id, assumption_set_id, None)
        grid = sensitivity(history, a, steps)
        if grid is None:
            raise EntityNotFound("No revenue history for sensitivity analysis")
        price = await self.financials.price(company_id)
        return {"grid": grid.model_dump(),
                "current_price": str(price) if price else None}
