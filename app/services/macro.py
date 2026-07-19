"""Macro context for cost-of-capital: risk-free rate and benchmark selection.

Risk-free chain: FRED (key required) → Yahoo treasury index (^TNX, no key) →
documented default assumption. Every value carries its source so the WACC
trace shows exactly where Rf came from.
"""
from decimal import Decimal

import structlog

from app.core.config import Settings
from app.core.http import HttpClient
from app.providers.base import Region
from app.providers.yahoo import CHART_URL, HEADERS

log = structlog.get_logger(__name__)

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

BENCHMARKS = {Region.US: "^GSPC", Region.IN: "^NSEI", Region.GLOBAL: "^GSPC"}
FRED_10Y = {Region.US: "DGS10", Region.IN: "INDIRLTLT01STM", Region.GLOBAL: "DGS10"}
DEFAULT_RF = {Region.US: Decimal("0.042"), Region.IN: Decimal("0.070"),
              Region.GLOBAL: Decimal("0.045")}


class MacroService:
    def __init__(self, http: HttpClient, settings: Settings) -> None:
        self.http = http
        self.settings = settings

    async def risk_free_rate(self, region: Region) -> tuple[Decimal, str]:
        """Returns (annual rate as decimal, source label)."""
        if self.settings.fred_api_key:
            try:
                data = await self.http.get_json(FRED_URL, params={
                    "series_id": FRED_10Y.get(region, "DGS10"),
                    "api_key": self.settings.fred_api_key,
                    "file_type": "json", "sort_order": "desc", "limit": 5,
                })
                for obs in data.get("observations", []):
                    if obs.get("value") not in (None, "", "."):
                        return (Decimal(obs["value"]) / 100,
                                f"FRED:{FRED_10Y.get(region, 'DGS10')}")
            except Exception as exc:
                log.warning("fred_rf_failed", error=str(exc)[:200])

        if region in (Region.US, Region.GLOBAL):
            try:
                data = await self.http.get_json(
                    CHART_URL.format(symbol="^TNX"),
                    params={"range": "5d", "interval": "1d"}, headers=HEADERS)
                meta = (data.get("chart", {}).get("result") or [{}])[0].get("meta", {})
                px = meta.get("regularMarketPrice")
                if px:
                    # ^TNX quotes the 10Y yield in percent (e.g. 4.28)
                    rate = Decimal(str(px)) / 100
                    if rate > Decimal("0.25"):   # legacy ×10 quotation guard
                        rate = rate / 10
                    return rate, "yahoo:^TNX"
            except Exception as exc:
                log.warning("tnx_rf_failed", error=str(exc)[:200])

        return DEFAULT_RF.get(region, DEFAULT_RF[Region.GLOBAL]), "assumption:default"

    def benchmark_symbol(self, region: Region) -> str:
        return BENCHMARKS.get(region, "^GSPC")

    async def benchmark_series(self, region: Region, range_: str = "5y") -> dict:
        """Benchmark index closes straight from Yahoo (indices are not
        companies; they are not persisted in the listings universe)."""
        symbol = self.benchmark_symbol(region)
        data = await self.http.get_json(
            CHART_URL.format(symbol=symbol),
            params={"range": range_, "interval": "1d"}, headers=HEADERS)
        result = (data.get("chart", {}).get("result") or [{}])[0]
        timestamps = result.get("timestamp") or []
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        return {"symbol": symbol, "timestamps": timestamps, "closes": closes}
