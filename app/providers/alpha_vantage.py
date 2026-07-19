"""Alpha Vantage adapter. Free tier is 25 requests/day — the budget in
rate_limit reflects that, so the chain naturally spares it for gaps Yahoo and
Stooq cannot fill."""
from datetime import UTC, datetime
from decimal import Decimal

from app.core.control import RateLimit
from app.providers.base import (
    Capability,
    NotSupported,
    OhlcvBar,
    ProviderAdapter,
    ProviderError,
    QuoteDTO,
    Region,
    SymbolCandidate,
    SymbolRef,
)

BASE_URL = "https://www.alphavantage.co/query"

REGION_MAP = {
    "United States": (Region.US, "NASDAQ"),
    "India/Bombay": (Region.IN, "BSE"),
    "India/National": (Region.IN, "NSE"),
    "United Kingdom": (Region.GLOBAL, "LSE"),
}


class AlphaVantageAdapter(ProviderAdapter):
    name = "alpha_vantage"
    capabilities = frozenset(
        {Capability.SYMBOL_SEARCH, Capability.OHLCV_DAILY, Capability.QUOTE}
    )
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=5, per_day=25)

    def __init__(self, http, api_key: str) -> None:  # type: ignore[no-untyped-def]
        super().__init__(http)
        self.api_key = api_key

    async def _query(self, params: dict) -> dict:
        data = await self.http.get_json(
            BASE_URL, params={**params, "apikey": self.api_key}
        )
        # AV signals quota/errors inside a 200 body.
        for key in ("Note", "Information", "Error Message"):
            if key in data:
                raise ProviderError(self.name, str(data[key])[:200])
        return data

    def _symbol(self, ref: SymbolRef) -> str:
        exchange = ref.exchange.upper()
        if exchange in ("NASDAQ", "NYSE", "NYSEARCA", "AMEX", "BATS"):
            return ref.ticker
        if exchange == "BSE":
            return f"{ref.ticker}.BSE"
        raise NotSupported(self.name, f"exchange {exchange} not covered")

    async def search(self, query: str) -> list[SymbolCandidate]:
        data = await self._query({"function": "SYMBOL_SEARCH", "keywords": query})
        out: list[SymbolCandidate] = []
        for m in data.get("bestMatches", []):
            if m.get("3. type") != "Equity":
                continue
            region, default_exchange = REGION_MAP.get(
                m.get("4. region", ""), (Region.GLOBAL, "UNKNOWN")
            )
            symbol = m["1. symbol"]
            out.append(SymbolCandidate(
                symbol=symbol,
                ticker=symbol.split(".")[0],
                name=m.get("2. name", symbol),
                exchange=default_exchange,
                region=region,
                currency=m.get("8. currency"),
                provider=self.name,
                score=float(m.get("9. matchScore", 0)),
            ))
        return out

    async def daily_ohlcv(self, ref: SymbolRef, lookback_days: int) -> list[OhlcvBar]:
        data = await self._query({
            "function": "TIME_SERIES_DAILY",
            "symbol": self._symbol(ref),
            "outputsize": "compact" if lookback_days <= 100 else "full",
        })
        series = data.get("Time Series (Daily)")
        if not series:
            raise ProviderError(self.name, f"no daily series for {self._symbol(ref)}")
        bars = [
            OhlcvBar(
                date=datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=UTC).date(),
                open=Decimal(row["1. open"]),
                high=Decimal(row["2. high"]),
                low=Decimal(row["3. low"]),
                close=Decimal(row["4. close"]),
                adj_close=None,  # adjusted series is premium-tier on AV
                volume=int(row["5. volume"]),
            )
            for day, row in sorted(series.items())
        ]
        return bars

    async def quote(self, ref: SymbolRef) -> QuoteDTO:
        data = await self._query({"function": "GLOBAL_QUOTE", "symbol": self._symbol(ref)})
        q = data.get("Global Quote") or {}
        price = q.get("05. price")
        if not price:
            raise ProviderError(self.name, f"no quote for {self._symbol(ref)}")
        change = q.get("10. change percent", "").rstrip("%")
        return QuoteDTO(
            price=Decimal(price),
            change_pct=Decimal(change) if change else None,
            as_of=datetime.now(UTC),
        )
