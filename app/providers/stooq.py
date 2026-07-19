"""Stooq adapter — free, no key, plain CSV. Reliable US EOD fallback when
Yahoo is throttled. US symbols map to '<ticker>.us'."""
import csv
import io
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.core.control import RateLimit
from app.providers.base import (
    Capability,
    NotSupported,
    OhlcvBar,
    ProviderAdapter,
    ProviderError,
    Region,
    SymbolRef,
)

DAILY_URL = "https://stooq.com/q/d/l/"


class StooqAdapter(ProviderAdapter):
    name = "stooq"
    capabilities = frozenset({Capability.OHLCV_DAILY})
    regions = frozenset({Region.US})
    rate_limit = RateLimit(per_minute=20, per_day=2000)

    def _symbol(self, ref: SymbolRef) -> str:
        if ref.exchange.upper() in ("NASDAQ", "NYSE", "NYSEARCA", "AMEX", "BATS"):
            return f"{ref.ticker.lower()}.us"
        raise NotSupported(self.name, f"exchange {ref.exchange} not covered")

    async def daily_ohlcv(self, ref: SymbolRef, lookback_days: int) -> list[OhlcvBar]:
        start = date.today() - timedelta(days=lookback_days)
        text = await self.http.get_text(
            DAILY_URL,
            params={
                "s": self._symbol(ref),
                "i": "d",
                "d1": start.strftime("%Y%m%d"),
                "d2": date.today().strftime("%Y%m%d"),
            },
        )
        if not text or text.lstrip().startswith("<") or "No data" in text:
            raise ProviderError(self.name, f"no data for {self._symbol(ref)}")

        bars: list[OhlcvBar] = []
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                close = Decimal(row["Close"])
            except (KeyError, ArithmeticError, ValueError):
                continue
            volume = row.get("Volume")
            bars.append(OhlcvBar(
                date=datetime.strptime(row["Date"], "%Y-%m-%d")
                .replace(tzinfo=UTC).date(),
                open=Decimal(row["Open"]) if row.get("Open") else None,
                high=Decimal(row["High"]) if row.get("High") else None,
                low=Decimal(row["Low"]) if row.get("Low") else None,
                close=close,
                # Stooq daily closes are split-adjusted; dividends are not
                # reflected, so adj_close is left unset rather than misstated.
                adj_close=None,
                volume=int(Decimal(volume)) if volume else None,
            ))
        if not bars:
            raise ProviderError(self.name, f"empty CSV for {self._symbol(ref)}")
        return bars
