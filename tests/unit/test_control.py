from app.core.control import MemoryControlPlane, RateLimit


async def test_per_minute_budget_enforced():
    plane = MemoryControlPlane()
    limit = RateLimit(per_minute=2, per_day=100)
    assert await plane.allow_request("prov", limit) is True
    assert await plane.allow_request("prov", limit) is True
    assert await plane.allow_request("prov", limit) is False


async def test_daily_budget_enforced_independently():
    plane = MemoryControlPlane()
    limit = RateLimit(per_minute=100, per_day=1)
    assert await plane.allow_request("prov", limit) is True
    assert await plane.allow_request("prov", limit) is False


async def test_circuit_opens_after_threshold_and_success_resets():
    plane = MemoryControlPlane(failure_threshold=3, cooldown_seconds=60)
    for _ in range(2):
        await plane.record_failure("prov")
    assert await plane.is_open("prov") is False
    await plane.record_success("prov")          # resets the count
    for _ in range(2):
        await plane.record_failure("prov")
    assert await plane.is_open("prov") is False
    await plane.record_failure("prov")          # third consecutive → opens
    assert await plane.is_open("prov") is True
    assert await plane.breaker_state("prov") == "open"
