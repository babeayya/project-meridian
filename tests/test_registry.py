"""Fallback-chain semantics: failures cascade, budgets skip, all-fail raises."""
import pytest

from app.core.control import MemoryControlPlane, RateLimit
from app.core.errors import DataUnavailable
from app.providers.base import Capability, NotSupported, ProviderAdapter, Region
from app.providers.registry import ProviderRegistry


class FakeAdapter(ProviderAdapter):
    regions = frozenset({Region.GLOBAL})
    capabilities = frozenset({Capability.OHLCV_DAILY})
    rate_limit = RateLimit(per_minute=100)

    def __init__(self, name: str, behavior: str) -> None:  # no http needed
        self.name = name
        self.behavior = behavior
        self.calls = 0

    async def daily_ohlcv(self, ref=None, lookback_days: int = 0):
        self.calls += 1
        if self.behavior == "fail":
            raise RuntimeError("boom")
        if self.behavior == "unsupported":
            raise NotSupported(self.name, "nope")
        return ["bar"]


def make_registry(*adapters, plane=None):
    plane = plane or MemoryControlPlane()
    chains = {Capability.OHLCV_DAILY: [a.name for a in adapters]}
    return ProviderRegistry(list(adapters), plane, chains=chains), plane


async def test_first_success_wins():
    a, b = FakeAdapter("a", "ok"), FakeAdapter("b", "ok")
    registry, _ = make_registry(a, b)
    result, provider = await registry.call(
        Capability.OHLCV_DAILY, Region.US, "daily_ohlcv", lookback_days=5
    )
    assert provider == "a" and result == ["bar"]
    assert b.calls == 0


async def test_failure_falls_through_to_next():
    a, b = FakeAdapter("a", "fail"), FakeAdapter("b", "ok")
    registry, _ = make_registry(a, b)
    result, provider = await registry.call(
        Capability.OHLCV_DAILY, Region.US, "daily_ohlcv", lookback_days=5
    )
    assert provider == "b"


async def test_not_supported_is_silent_skip():
    a, b = FakeAdapter("a", "unsupported"), FakeAdapter("b", "ok")
    registry, _ = make_registry(a, b)
    _, provider = await registry.call(
        Capability.OHLCV_DAILY, Region.US, "daily_ohlcv", lookback_days=5
    )
    assert provider == "b"


async def test_all_fail_raises_data_unavailable_with_providers_tried():
    a, b = FakeAdapter("a", "fail"), FakeAdapter("b", "fail")
    registry, _ = make_registry(a, b)
    with pytest.raises(DataUnavailable) as exc:
        await registry.call(Capability.OHLCV_DAILY, Region.US,
                            "daily_ohlcv", lookback_days=5)
    tried = exc.value.extra["providers_tried"]
    assert any("a" in t for t in tried) and any("b" in t for t in tried)


async def test_open_circuit_skips_provider():
    a, b = FakeAdapter("a", "ok"), FakeAdapter("b", "ok")
    plane = MemoryControlPlane(failure_threshold=1, cooldown_seconds=60)
    registry, _ = make_registry(a, b, plane=plane)
    await plane.record_failure("a")  # opens immediately (threshold=1)
    _, provider = await registry.call(
        Capability.OHLCV_DAILY, Region.US, "daily_ohlcv", lookback_days=5
    )
    assert provider == "b"
    assert a.calls == 0


async def test_exhausted_budget_skips_provider():
    a, b = FakeAdapter("a", "ok"), FakeAdapter("b", "ok")
    a.rate_limit = RateLimit(per_minute=0)
    registry, _ = make_registry(a, b)
    _, provider = await registry.call(
        Capability.OHLCV_DAILY, Region.US, "daily_ohlcv", lookback_days=5
    )
    assert provider == "b"
    assert a.calls == 0
