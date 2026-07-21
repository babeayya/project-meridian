"""Beta is taken from the providers, not regressed locally.

Fitting our own left the terminal disagreeing with every screen a user could
check it against, and a throttled benchmark response could collapse the
regression window and yield 0.23 for a stock published at 0.98.
"""
from decimal import Decimal

import pytest

from app.providers.base import Capability, ProviderError, Region, SymbolRef
from app.providers.registry import DEFAULT_CHAINS
from app.providers.yahoo import YahooAdapter
from app.services.valuation_service import BETA_SANITY_MAX, BETA_SANITY_MIN


class StubHttp:
    """Minimal HttpClient stand-in: quoteSummary payload plus a crumb."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.crumb_calls = 0

    async def get(self, url: str, **kwargs):      # cookie seeding
        return None

    async def get_text(self, url: str, **kwargs) -> str:
        self.crumb_calls += 1
        return "a-crumb"

    async def get_json(self, url: str, **kwargs):
        return self.payload


def _summary(beta) -> dict:
    return {"quoteSummary": {"result": [{"defaultKeyStatistics": {"beta": beta}}]}}


REF = SymbolRef(ticker="JPM", exchange="NYSE", yahoo_symbol="JPM", region=Region.US)


async def test_beta_parsed_from_yahoos_raw_field():
    adapter = YahooAdapter(StubHttp(_summary({"raw": 0.982, "fmt": "0.98"})))
    assert await adapter.beta(REF) == Decimal("0.982")


async def test_beta_parsed_when_returned_bare():
    adapter = YahooAdapter(StubHttp(_summary(1.13)))
    assert await adapter.beta(REF) == Decimal("1.13")


async def test_missing_beta_is_an_error_not_a_zero():
    """A silent 0 would zero out the equity risk premium in CAPM."""
    adapter = YahooAdapter(StubHttp(_summary(None)))
    with pytest.raises(ProviderError):
        await adapter.beta(REF)


async def test_empty_result_is_an_error():
    adapter = YahooAdapter(StubHttp({"quoteSummary": {"result": []}}))
    with pytest.raises(ProviderError):
        await adapter.beta(REF)


async def test_crumb_is_cached_across_calls():
    """Minting a crumb costs two extra requests against a 30/min budget."""
    http = StubHttp(_summary(0.982))
    adapter = YahooAdapter(http)
    await adapter.beta(REF)
    await adapter.beta(REF)
    assert http.crumb_calls == 1


def test_sanity_band_brackets_real_published_betas():
    """Observed on 2026-07-21: Reliance 0.184 is the low end of what providers
    genuinely publish, so the floor must not reject it."""
    for published in ("0.184", "0.422", "0.982", "1.097", "1.13"):
        assert BETA_SANITY_MIN <= Decimal(published) <= BETA_SANITY_MAX
    assert not BETA_SANITY_MIN <= Decimal("0") <= BETA_SANITY_MAX
    assert not BETA_SANITY_MIN <= Decimal("12") <= BETA_SANITY_MAX


def test_beta_chain_is_registered():
    """An unregistered capability yields an empty chain and every lookup fails
    with 'All providers failed' — which is how this shipped broken once."""
    assert DEFAULT_CHAINS[Capability.BETA] == ["yahoo", "fmp"]
