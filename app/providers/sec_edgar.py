"""SEC EDGAR companyfacts adapter — authoritative XBRL statements for US
filers. No key; SEC requires a descriptive User-Agent. Annual (10-K) data.
"""
from datetime import date
from decimal import Decimal

from app.core.control import RateLimit
from app.core.http import HttpClient
from app.providers.base import (
    Capability,
    NotSupported,
    ProviderAdapter,
    ProviderError,
    Region,
    StatementPeriodDTO,
    SymbolRef,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:0>10}.json"

# canonical key → ordered us-gaap tag candidates (first hit wins)
GAAP_MAP: dict[str, list[str]] = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "SalesRevenueNet"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "rnd_expense": ["ResearchAndDevelopmentExpense"],
    "sga_expense": ["SellingGeneralAndAdministrativeExpense"],
    "operating_income": ["OperatingIncomeLoss"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization",
                                  "DepreciationAndAmortization",
                                  "DepreciationAmortizationAndAccretionNet"],
    "stock_compensation": ["ShareBasedCompensation"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "share_repurchase": ["PaymentsForRepurchaseOfCommonStock"],
    "cash_and_equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "short_term_investments": ["MarketableSecuritiesCurrent", "ShortTermInvestments"],
    "receivables": ["AccountsReceivableNetCurrent"],
    "inventory": ["InventoryNet"],
    "current_assets": ["AssetsCurrent"],
    "net_ppe": ["PropertyPlantAndEquipmentNet"],
    "goodwill": ["Goodwill"],
    "intangibles": ["FiniteLivedIntangibleAssetsNet", "IntangibleAssetsNetExcludingGoodwill"],
    "total_assets": ["Assets"],
    "accounts_payable": ["AccountsPayableCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "total_liabilities": ["Liabilities"],
    "total_equity": ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "minority_interest": ["MinorityInterest"],
}


class SecEdgarAdapter(ProviderAdapter):
    name = "sec_edgar"
    capabilities = frozenset({Capability.STATEMENTS_ANNUAL})
    regions = frozenset({Region.US})
    rate_limit = RateLimit(per_minute=300, per_day=20000)  # SEC guideline 10 req/s

    def __init__(self, http: HttpClient, user_agent: str) -> None:
        super().__init__(http)
        self.headers = {"User-Agent": user_agent}
        self._cik_cache: dict[str, str] | None = None

    async def _cik_for(self, ticker: str) -> str:
        if self._cik_cache is None:
            data = await self.http.get_json(TICKERS_URL, headers=self.headers)
            self._cik_cache = {
                row["ticker"].upper(): str(row["cik_str"])
                for row in data.values()
            }
        cik = self._cik_cache.get(ticker.upper())
        if not cik:
            raise NotSupported(self.name, f"{ticker} not an SEC filer")
        return cik

    async def statements(self, ref: SymbolRef, period_type: str,
                         cik: str | None = None) -> list[StatementPeriodDTO]:
        if period_type != "annual":
            raise NotSupported(self.name, "quarterly derivation not implemented; "
                                          "chain falls through to Yahoo")
        if ref.region != Region.US:
            raise NotSupported(self.name, "US filers only")
        cik = cik or await self._cik_for(ref.ticker)
        data = await self.http.get_json(FACTS_URL.format(cik=int(cik)),
                                        headers=self.headers)
        gaap = data.get("facts", {}).get("us-gaap", {})
        if not gaap:
            raise ProviderError(self.name, f"no us-gaap facts for CIK {cik}")

        # periods keyed by fiscal period end date. NOTE: the fact's "fy" field
        # is the FILING's fiscal year (comparative years inherit it), so the
        # period's fiscal year is derived from its end date instead.
        periods: dict[date, dict[str, Decimal]] = {}
        for canonical, tags in GAAP_MAP.items():
            for tag in tags:
                units = gaap.get(tag, {}).get("units", {})
                series = units.get("USD") or units.get("USD/shares") or units.get("shares")
                if not series:
                    continue
                # annual facts from 10-K filings; keep the latest-filed value per FY end
                best: dict[date, tuple[str, Decimal]] = {}
                for fact in series:
                    if fact.get("form") not in ("10-K", "10-K/A", "20-F"):
                        continue
                    if fact.get("fp") != "FY":
                        continue
                    end = date.fromisoformat(fact["end"])
                    # flow facts must cover ~a year; instant facts have no start
                    if "start" in fact:
                        start = date.fromisoformat(fact["start"])
                        if (end - start).days < 300:
                            continue
                    filed = fact.get("filed", "1900-01-01")
                    val = Decimal(str(fact["val"]))
                    prev = best.get(end)
                    if prev is None or filed > prev[0]:
                        best[end] = (filed, val)
                for end, (_, val) in best.items():
                    periods.setdefault(end, {})
                    if canonical not in periods[end]:
                        periods[end][canonical] = val
                if any(canonical in items for items in periods.values()):
                    break  # first tag with data wins for this canonical key

        out = [
            StatementPeriodDTO(
                fiscal_year=end.year, period_end=end,
                period_type="annual", currency="USD", items=items,
                source_url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):0>10}.json",
            )
            for end, items in periods.items()
            if "revenue" in items or "total_assets" in items  # reject empty shells
        ]
        out.sort(key=lambda p: p.period_end)
        if not out:
            raise ProviderError(self.name, f"no annual periods extracted for CIK {cik}")
        return out[-12:]
