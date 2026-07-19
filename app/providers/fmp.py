"""Financial Modeling Prep adapter — 'stable' API (the current surface for
free-tier keys; the legacy /api/v3 endpoints return 403 for new accounts).
Statements fallback behind EDGAR/Yahoo."""
from datetime import date
from decimal import Decimal

from app.core.control import RateLimit
from app.providers.base import (
    Capability,
    NotSupported,
    ProviderAdapter,
    ProviderError,
    Region,
    StatementPeriodDTO,
    SymbolRef,
)

BASE = "https://financialmodelingprep.com/stable"

INCOME_MAP = {
    "revenue": "revenue", "cost_of_revenue": "costOfRevenue",
    "gross_profit": "grossProfit",
    "rnd_expense": "researchAndDevelopmentExpenses",
    "sga_expense": "sellingGeneralAndAdministrativeExpenses",
    "operating_income": "operatingIncome", "interest_expense": "interestExpense",
    "pretax_income": "incomeBeforeTax", "income_tax": "incomeTaxExpense",
    "net_income": "netIncome", "eps_diluted": "epsDiluted",
    "shares_diluted": "weightedAverageShsOutDil",
    "depreciation_amortization": "depreciationAndAmortization",
}
BALANCE_MAP = {
    "cash_and_equivalents": "cashAndCashEquivalents",
    "short_term_investments": "shortTermInvestments",
    "receivables": "netReceivables", "inventory": "inventory",
    "current_assets": "totalCurrentAssets", "net_ppe": "propertyPlantEquipmentNet",
    "goodwill": "goodwill", "intangibles": "intangibleAssets",
    "total_assets": "totalAssets", "accounts_payable": "accountPayables",
    "current_liabilities": "totalCurrentLiabilities",
    "short_term_debt": "shortTermDebt", "long_term_debt": "longTermDebt",
    "total_liabilities": "totalLiabilities",
    "total_equity": "totalStockholdersEquity",
    "retained_earnings": "retainedEarnings", "minority_interest": "minorityInterest",
}
CASHFLOW_MAP = {
    "operating_cash_flow": "operatingCashFlow", "capex": "capitalExpenditure",
    "dividends_paid": "netDividendsPaid",
    "share_repurchase": "commonStockRepurchased",
    "stock_compensation": "stockBasedCompensation",
    "change_in_working_capital": "changeInWorkingCapital",
}
NEGATIVE_FLOWS = {"capex", "dividends_paid", "share_repurchase"}


class FmpAdapter(ProviderAdapter):
    name = "fmp"
    capabilities = frozenset({Capability.STATEMENTS_ANNUAL,
                              Capability.STATEMENTS_QUARTERLY})
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=10, per_day=240)

    def __init__(self, http, api_key: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(http)
        self.api_key = api_key

    def _symbol(self, ref: SymbolRef) -> str:
        if ref.exchange.upper() == "NSE":
            return f"{ref.ticker}.NS"
        if ref.exchange.upper() == "BSE":
            return f"{ref.ticker}.BO"
        return ref.ticker

    async def _fetch(self, endpoint: str, symbol: str, period: str) -> list[dict]:
        data = await self.http.get_json(
            f"{BASE}/{endpoint}",
            params={"symbol": symbol, "period": period, "limit": 12,
                    "apikey": self.api_key},
        )
        if isinstance(data, dict):  # error payloads are dicts
            raise ProviderError(self.name, str(data)[:200])
        return data

    async def statements(self, ref: SymbolRef, period_type: str,
                         cik: str | None = None) -> list[StatementPeriodDTO]:
        period = "annual" if period_type == "annual" else "quarter"
        symbol = self._symbol(ref)
        income = await self._fetch("income-statement", symbol, period)
        balance = await self._fetch("balance-sheet-statement", symbol, period)
        cash = await self._fetch("cash-flow-statement", symbol, period)
        if not income:
            raise NotSupported(self.name, f"no statements for {symbol}")

        periods: dict[date, dict[str, Decimal]] = {}
        currency = income[0].get("reportedCurrency", "USD") or "USD"

        def absorb(rows: list[dict], mapping: dict[str, str]) -> None:
            for row in rows:
                end = date.fromisoformat(row["date"])
                items = periods.setdefault(end, {})
                for canonical, field in mapping.items():
                    v = row.get(field)
                    if v is None:
                        continue
                    val = Decimal(str(v))
                    if canonical in NEGATIVE_FLOWS:
                        val = abs(val)
                    items[canonical] = val

        absorb(income, INCOME_MAP)
        absorb(balance, BALANCE_MAP)
        absorb(cash, CASHFLOW_MAP)

        out = [
            StatementPeriodDTO(fiscal_year=end.year, period_end=end,
                               period_type=period_type, currency=currency,
                               items=items,
                               source_url=f"{BASE}/income-statement?symbol={symbol}")
            for end, items in sorted(periods.items()) if "revenue" in items
        ]
        if not out:
            raise ProviderError(self.name, f"empty statements for {symbol}")
        return out[-12:]
