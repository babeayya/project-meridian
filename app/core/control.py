"""Provider control plane: token-bucket rate limiting + circuit breakers.

Two implementations share one interface: Redis-backed (multi-process, prod) and
in-memory (single-process dev/tests, selected by REDIS_URL=memory:// or used as
automatic fallback when Redis is unreachable at startup).

Failure policy is fail-open: a broken control plane must never take the data
path down — a skipped rate check is logged, not fatal.
"""
import time
from dataclasses import dataclass
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RateLimit:
    per_minute: int
    per_day: int | None = None  # None = no daily budget


class ControlPlane(Protocol):
    async def allow_request(self, provider: str, limit: RateLimit) -> bool: ...
    async def is_open(self, provider: str) -> bool: ...
    async def record_failure(self, provider: str) -> None: ...
    async def record_success(self, provider: str) -> None: ...
    async def breaker_state(self, provider: str) -> str: ...
    async def ping(self) -> bool: ...


class MemoryControlPlane:
    """Single-process control plane. Windows are [start, start+seconds)."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 300) -> None:
        self._counters: dict[str, tuple[float, int]] = {}  # key -> (window_start, count)
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    def _bump(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        start, count = self._counters.get(key, (now, 0))
        if now - start >= window_seconds:
            start, count = now, 0
        count += 1
        self._counters[key] = (start, count)
        return count

    async def allow_request(self, provider: str, limit: RateLimit) -> bool:
        if self._bump(f"{provider}:m", 60) > limit.per_minute:
            return False
        if limit.per_day is not None and self._bump(f"{provider}:d", 86400) > limit.per_day:
            return False
        return True

    async def is_open(self, provider: str) -> bool:
        return time.monotonic() < self._open_until.get(provider, 0.0)

    async def record_failure(self, provider: str) -> None:
        n = self._failures.get(provider, 0) + 1
        self._failures[provider] = n
        if n >= self.failure_threshold:
            self._open_until[provider] = time.monotonic() + self.cooldown_seconds
            self._failures[provider] = 0
            log.warning("circuit_opened", provider=provider,
                        cooldown_s=self.cooldown_seconds)

    async def record_success(self, provider: str) -> None:
        self._failures.pop(provider, None)

    async def breaker_state(self, provider: str) -> str:
        return "open" if await self.is_open(provider) else "closed"

    async def ping(self) -> bool:
        return True


class RedisControlPlane:
    def __init__(self, redis_url: str, failure_threshold: int = 5,
                 cooldown_seconds: int = 300) -> None:
        import redis.asyncio as aioredis

        self._r = aioredis.from_url(redis_url, decode_responses=True)
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

    async def _bump(self, key: str, window_seconds: int) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = await pipe.execute()
        return int(count)

    async def allow_request(self, provider: str, limit: RateLimit) -> bool:
        try:
            minute_bucket = int(time.time() // 60)
            if await self._bump(f"rl:{provider}:m:{minute_bucket}", 90) > limit.per_minute:
                return False
            if limit.per_day is not None:
                day_bucket = int(time.time() // 86400)
                if await self._bump(f"rl:{provider}:d:{day_bucket}", 90000) > limit.per_day:
                    return False
            return True
        except Exception as exc:  # fail-open
            log.warning("control_plane_error", op="allow_request", error=str(exc))
            return True

    async def is_open(self, provider: str) -> bool:
        try:
            return bool(await self._r.exists(f"cb:{provider}:open"))
        except Exception:
            return False

    async def record_failure(self, provider: str) -> None:
        try:
            key = f"cb:{provider}:fail"
            pipe = self._r.pipeline()
            pipe.incr(key)
            pipe.expire(key, 600, nx=True)
            n, _ = await pipe.execute()
            if int(n) >= self.failure_threshold:
                await self._r.set(f"cb:{provider}:open", "1", ex=self.cooldown_seconds)
                await self._r.delete(key)
                log.warning("circuit_opened", provider=provider,
                            cooldown_s=self.cooldown_seconds)
        except Exception as exc:
            log.warning("control_plane_error", op="record_failure", error=str(exc))

    async def record_success(self, provider: str) -> None:
        try:
            await self._r.delete(f"cb:{provider}:fail")
        except Exception:
            pass

    async def breaker_state(self, provider: str) -> str:
        return "open" if await self.is_open(provider) else "closed"

    async def ping(self) -> bool:
        try:
            return bool(await self._r.ping())
        except Exception:
            return False


async def build_control_plane(redis_url: str, failure_threshold: int,
                              cooldown_seconds: int) -> ControlPlane:
    if redis_url.startswith("memory://"):
        return MemoryControlPlane(failure_threshold, cooldown_seconds)
    plane = RedisControlPlane(redis_url, failure_threshold, cooldown_seconds)
    if await plane.ping():
        return plane
    log.warning("redis_unreachable_falling_back_to_memory", redis_url=redis_url)
    return MemoryControlPlane(failure_threshold, cooldown_seconds)
