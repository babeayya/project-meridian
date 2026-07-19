"""Yahoo Finance adapter (unauthenticated public endpoints).

First in most chains: no key, global coverage including NSE (.NS) / BSE (.BO).
"""
from datetime import UTC, datetime
from decimal import Decimal

from app.core.control import RateLimit
from app.providers.base import (
    Capability,
    OhlcvBar,
    ProviderAdapter,
    ProviderError,
    QuoteDTO,
    Region,
    SymbolCandidate,
    SymbolRef,
)

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

# Yahoo requires a browser-like UA; default python UA gets 429/403.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# Yahoo exchange codes → normalized exchange names
EXCHANGE_MAP = {
    "NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ",
    "NYQ": "NYSE", "PCX": "NYSEARCA", "ASE": "AMEX", "BTS": "BATS",
    "NSI": "NSE", "BSE": "BSE", "BOM": "BSE",
    "LSE": "LSE", "TOR": "TSX", "FRA": "FRA", "GER": "XETRA",
    "JPX": "TSE", "HKG": "HKEX", "SES": "SGX",
}

_RANGE_STEPS = [(7, "5d"), (30, "1mo"), (95, "3mo"), (185, "6mo"),
                (370, "1y"), (740, "2y"), (1830, "5y"), (3660, "10y")]


def _range_for(lookback_days: int) -> str:
    for days, label in _RANGE_STEPS:
        if lookback_days <= days:
            return label
    return "max"


class YahooAdapter(ProviderAdapter):
    name = "yahoo"
    capabilities = frozenset(
        {Capability.SYMBOL_SEARCH, Capability.OHLCV_DAILY, Capability.QUOTE}
    )
    regions = frozenset({Region.GLOBAL})
    rate_limit = RateLimit(per_minute=30, per_day=5000)

    def _symbol(self, ref: SymbolRef) -> str:
        if ref.yahoo_symbol:
            return ref.yahoo_symbol
        suffix = {"NSE": ".NS", "BSE": ".BO"}.get(ref.exchange.upper(), "")
        return f"{ref.ticker}{suffix}"

    async def search(self, query: str) -> list[SymbolCandidate]:
        data = await self.http.get_json(
            SEARCH_URL,
            params={"q": query, "quotesCount": 10, "newsCount": 0,
                    "listsCount": 0, "enableFuzzyQuery": "true"},
            headers=HEADERS,
        )
        out: list[SymbolCandidate] = []
        for q in data.get("quotes", []):
            if q.get("quoteType") != "EQUITY" or not q.get("symbol"):
                continue
            exchange = EXCHANGE_MAP.get(q.get("exchange", ""), q.get("exchange", "UNKNOWN"))
            symbol = q["symbol"]
            region = (
                Region.IN if exchange in ("NSE", "BSE")
                else Region.US if exchange in ("NASDAQ", "NYSE", "NYSEARCA", "AMEX", "BATS")
                else Region.GLOBAL
            )
            out.append(SymbolCandidate(
                symbol=symbol,
                ticker=symbol.split(".")[0],
                name=q.get("longname") or q.get("shortname") or symbol,
                exchange=exchange,
                region=region,
                quote_type=q["quoteType"],
                provider=self.name,
                score=float(q.get("score", 0)),
            ))
        return out

    async def _chart(self, symbol: str, range_: str) -> dict:
        data = await self.http.get_json(
            CHART_URL.format(symbol=symbol),
            params={"range": range_, "interval": "1d", "events": "div,split"},
            headers=HEADERS,
        )
        chart = data.get("chart", {})
        if chart.get("error"):
            raise ProviderError(self.name, str(chart["error"]))
        results = chart.get("result") or []
        if not results:
            raise ProviderError(self.name, f"empty chart result for {symbol}")
        return results[0]

    async def daily_ohlcv(self, ref: SymbolRef, lookback_days: int) -> list[OhlcvBar]:
        result = self._parse_bars(await self._chart(self._symbol(ref), _range_for(lookback_days)))
        if not result:
            raise ProviderError(self.name, f"no bars for {self._symbol(ref)}")
        return result

    @staticmethod
    def _at(seq: list | None, i: int) -> Decimal | None:
        v = seq[i] if seq and i < len(seq) else None
        return Decimal(str(round(v, 6))) if v is not None else None

    @classmethod
    def _parse_bars(cls, result: dict) -> list[OhlcvBar]:
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators", {}).get("quote") or [{}])[0]
        adj = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose") or []
        bars: list[OhlcvBar] = []
        for i, ts in enumerate(timestamps):
            close = cls._at(quote.get("close"), i)
            if close is None:
                continue  # holiday / null row
            volumes = quote.get("volume") or []
            volume = volumes[i] if i < len(volumes) else None
            bars.append(OhlcvBar(
                date=datetime.fromtimestamp(ts, tz=UTC).date(),
                open=cls._at(quote.get("open"), i),
                high=cls._at(quote.get("high"), i),
                low=cls._at(quote.get("low"), i),
                close=close,
                adj_close=cls._at(adj, i),
                volume=int(volume) if volume else None,
            ))
        return bars

    async def quote(self, ref: SymbolRef) -> QuoteDTO:
        meta = (await self._chart(self._symbol(ref), "1d")).get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            raise ProviderError(self.name, f"no market price for {self._symbol(ref)}")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        change = (
            Decimal(str(round((price - prev) / prev * 100, 4)))
            if prev else None
        )
        return QuoteDTO(
            price=Decimal(str(price)),
            currency=meta.get("currency"),
            change_pct=change,
            as_of=datetime.now(UTC),
        )
