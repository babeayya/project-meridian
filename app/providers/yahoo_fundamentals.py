"""Yahoo fundamentals-timeseries adapter: global coverage (incl. NSE/BSE),
annual + quarterly statements, dividends/splits via chart events, and the
search endpoint's news feed. Split out from the price adapter so each keeps
one job."""
import hashlib
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.control import RateLimit
from app.providers.base import (
    Capability,
    DividendDTO,
    NewsItemDTO,
    ProviderAdapter,
    ProviderError,
    Region,
    SplitDTO,
    StatementPeriodDTO,
    SymbolRef,
)
from app.providers.yahoo import CHART_URL, HEADERS, SEARCH_URL

TS_URL = "https://query1.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{symbol}"

# canonical key → Yahoo timeseries metric (prefixed annual*/quarterly*)
YAHOO_MAP: dict[str, str] = {
    "revenue": "TotalRevenue",
    "cost_of_revenue": "CostOfRevenue",
    "gross_profit": "GrossProfit",
    "rnd_expense": "ResearchAndDevelopment",
    "sga_expense": "SellingGeneralAndAdministration",
    "operating_income": "OperatingIncome",
    "interest_expense": "InterestExpense",
    "pretax_income": "PretaxIncome",
    "income_tax": "TaxProvision",
    "net_income": "NetIncome",
    "eps_diluted": "DilutedEPS",
    "shares_diluted": "DilutedAverageShares",
    "depreciation_amortization": "DepreciationAndAmortization",
    "stock_compensation": "StockBasedCompensation",
    "change_in_working_capital": "ChangeInWorkingCapital",
    "operating_cash_flow": "OperatingCashFlow",
    "capex": "CapitalExpenditure",
    "dividends_paid": "CashDividendsPaid",
    "share_repurchase": "RepurchaseOfCapitalStock",
    "cash_and_equivalents": "CashAndCashEquivalents",
    "short_term_investments": "OtherShortTermInvestments",
    "receivables": "AccountsReceivable",
    "inventory": "Inventory",
    "current_assets": "CurrentAssets",
    "net_ppe": "NetPPE",
    "goodwill": "Goodwill",
    "intangibles": "OtherIntangibleAssets",
    "total_assets": "TotalAssets",
    "accounts_payable": "AccountsPayable",
    "current_liabilities": "CurrentLiabilities",
    "short_term_debt": "CurrentDebt",
    "long_term_debt": "LongTermDebt",
    "total_liabilities": "TotalLiabilitiesNetMinorityInterest",
    "total_equity": "StockholdersEquity",
    "retained_earnings": "RetainedEarnings",
    "minority_interest": "MinorityInterest",
}
# Yahoo reports these as negative cash outflows; taxonomy stores magnitudes.
NEGATIVE_FLOWS = {"capex", "dividends_paid", "share_repurchase"}


class YahooFundamentalsAdapter(ProviderAdapter):
    name = "yahoo_fundamentals"
    capabilities = frozenset({
        Capability.STATEMENTS_ANNUAL, Capability.STATEMENTS_QUARTERLY,
        Capability.DIVIDENDS, Capability.SPLITS, Capability.NEWS,
    })
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=20, per_day=2000)

    def _symbol(self, ref: SymbolRef) -> str:
        if ref.yahoo_symbol:
            return ref.yahoo_symbol
        suffix = {"NSE": ".NS", "BSE": ".BO"}.get(ref.exchange.upper(), "")
        return f"{ref.ticker}{suffix}"

    async def statements(self, ref: SymbolRef, period_type: str,
                         cik: str | None = None) -> list[StatementPeriodDTO]:
        prefix = "annual" if period_type == "annual" else "quarterly"
        symbol = self._symbol(ref)
        types = ",".join(f"{prefix}{v}" for v in YAHOO_MAP.values())
        now = int(datetime.now(UTC).timestamp())
        data = await self.http.get_json(
            TS_URL.format(symbol=symbol),
            params={"symbol": symbol, "type": types, "merge": "false",
                    "period1": now - 12 * 366 * 86400, "period2": now},
            headers=HEADERS,
        )
        results = data.get("timeseries", {}).get("result") or []
        if not results:
            raise ProviderError(self.name, f"no fundamentals for {symbol}")

        reverse = {f"{prefix}{v}": k for k, v in YAHOO_MAP.items()}
        periods: dict[date, dict[str, Decimal]] = {}
        currency: str = "USD"
        for block in results:
            ts_type = (block.get("meta", {}).get("type") or [""])[0]
            canonical = reverse.get(ts_type)
            rows = block.get(ts_type)
            if not canonical or not rows:
                continue
            for row in rows:
                if not row or row.get("reportedValue") is None:
                    continue
                end = date.fromisoformat(row["asOfDate"])
                val = Decimal(str(row["reportedValue"]["raw"]))
                if canonical in NEGATIVE_FLOWS:
                    val = abs(val)
                periods.setdefault(end, {})[canonical] = val
                if row.get("currencyCode"):
                    currency = row["currencyCode"]

        out = [
            StatementPeriodDTO(
                fiscal_year=end.year, period_end=end, period_type=period_type,
                currency=currency, items=items,
                source_url=f"https://finance.yahoo.com/quote/{symbol}/financials",
            )
            for end, items in sorted(periods.items())
            if "revenue" in items or "total_assets" in items
        ]
        if not out:
            raise ProviderError(self.name, f"empty statement set for {symbol}")
        return out[-12:]

    async def _chart_events(self, ref: SymbolRef, lookback_days: int) -> dict:
        range_ = "10y" if lookback_days > 1830 else "5y"
        data = await self.http.get_json(
            CHART_URL.format(symbol=self._symbol(ref)),
            params={"range": range_, "interval": "1mo", "events": "div,split"},
            headers=HEADERS,
        )
        results = data.get("chart", {}).get("result") or []
        if not results:
            raise ProviderError(self.name, f"no chart events for {self._symbol(ref)}")
        return results[0].get("events") or {}

    async def dividends(self, ref: SymbolRef, lookback_days: int) -> list[DividendDTO]:
        events = await self._chart_events(ref, lookback_days)
        divs = [
            DividendDTO(
                ex_date=datetime.fromtimestamp(int(d["date"]), tz=UTC).date(),
                amount=Decimal(str(d["amount"])),
            )
            for d in (events.get("dividends") or {}).values()
            if d.get("amount")
        ]
        divs.sort(key=lambda d: d.ex_date)
        return divs

    async def splits(self, ref: SymbolRef, lookback_days: int) -> list[SplitDTO]:
        events = await self._chart_events(ref, lookback_days)
        splits = [
            SplitDTO(
                ex_date=datetime.fromtimestamp(int(s["date"]), tz=UTC).date(),
                numerator=Decimal(str(s["numerator"])),
                denominator=Decimal(str(s["denominator"])),
            )
            for s in (events.get("splits") or {}).values()
            if s.get("numerator") and s.get("denominator")
        ]
        splits.sort(key=lambda s: s.ex_date)
        return splits

    async def news(self, query: str, company_name: str,
                   lookback_days: int) -> list[NewsItemDTO]:
        data = await self.http.get_json(
            SEARCH_URL,
            params={"q": query, "quotesCount": 0, "newsCount": 25, "listsCount": 0},
            headers=HEADERS,
        )
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        out = []
        for n in data.get("news", []):
            if not n.get("link") or not n.get("title"):
                continue
            published = None
            if n.get("providerPublishTime"):
                published = datetime.fromtimestamp(int(n["providerPublishTime"]), tz=UTC)
                if published < cutoff:
                    continue
            out.append(NewsItemDTO(
                url=n["link"], headline=n["title"],
                outlet=n.get("publisher"), published_at=published, language="en",
            ))
        return out


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()
