"""Fallback-chain executor.

Walks the configured chain for a capability, skipping providers whose circuit
is open or whose rate budget is exhausted, records success/failure into the
control plane, and logs every call. `call_all` fans out to every eligible
provider in parallel (used by entity resolution to merge candidates).
"""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from app.core.control import ControlPlane
from app.core.errors import DataUnavailable
from app.providers.base import Capability, NotSupported, ProviderAdapter, Region

log = structlog.get_logger(__name__)

# call_log(provider, method, ok, latency_ms, error)
CallLogger = Callable[[str, str, bool, int, str | None], Awaitable[None]]

DEFAULT_CHAINS: dict[Capability, list[str]] = {
    Capability.SYMBOL_SEARCH: ["yahoo", "alpha_vantage"],
    Capability.OHLCV_DAILY: ["yahoo", "stooq", "alpha_vantage"],
    Capability.QUOTE: ["yahoo", "alpha_vantage"],
    # EDGAR is authoritative for US annuals; Yahoo covers global + quarterly
    Capability.STATEMENTS_ANNUAL: ["sec_edgar", "yahoo_fundamentals", "fmp"],
    Capability.STATEMENTS_QUARTERLY: ["yahoo_fundamentals", "fmp"],
    # published beta, so the terminal agrees with the figure on the quote page
    Capability.BETA: ["yahoo", "fmp"],
    Capability.DIVIDENDS: ["yahoo_fundamentals"],
    Capability.SPLITS: ["yahoo_fundamentals"],
    Capability.NEWS: ["newsapi", "gdelt", "yahoo_fundamentals"],
}


class ProviderRegistry:
    def __init__(
        self,
        adapters: list[ProviderAdapter],
        control: ControlPlane,
        chains: dict[Capability, list[str]] | None = None,
        call_logger: CallLogger | None = None,
    ) -> None:
        self.adapters = {a.name: a for a in adapters}
        self.control = control
        self.chains = chains or DEFAULT_CHAINS
        self.call_logger = call_logger

    def _eligible(self, capability: Capability, region: Region) -> list[ProviderAdapter]:
        return [
            self.adapters[name]
            for name in self.chains.get(capability, [])
            if name in self.adapters and self.adapters[name].supports(capability, region)
        ]

    async def _log(self, provider: str, method: str, ok: bool,
                   latency_ms: int, error: str | None) -> None:
        log.info("provider_call", provider=provider, method=method, ok=ok,
                 latency_ms=latency_ms, error=error)
        if self.call_logger:
            try:
                await self.call_logger(provider, method, ok, latency_ms, error)
            except Exception as exc:  # DB logging must never break the data path
                log.warning("call_log_failed", error=str(exc))

    async def _invoke(self, adapter: ProviderAdapter, method: str,
                      kwargs: dict[str, Any]) -> Any:
        t0 = time.monotonic()
        try:
            result = await getattr(adapter, method)(**kwargs)
        except NotSupported:
            raise
        except Exception as exc:
            await self.control.record_failure(adapter.name)
            await self._log(adapter.name, method, False,
                            int((time.monotonic() - t0) * 1000), str(exc)[:300])
            raise
        await self.control.record_success(adapter.name)
        await self._log(adapter.name, method, True,
                        int((time.monotonic() - t0) * 1000), None)
        return result

    async def _gate(self, adapter: ProviderAdapter) -> str | None:
        """Returns a skip reason, or None if the adapter may be called."""
        if await self.control.is_open(adapter.name):
            return "circuit_open"
        if not await self.control.allow_request(adapter.name, adapter.rate_limit):
            return "rate_budget_exhausted"
        return None

    async def call(self, capability: Capability, region: Region,
                   method: str, **kwargs: Any) -> tuple[Any, str]:
        """First success along the chain wins. Returns (result, provider_name)."""
        tried: list[str] = []
        for adapter in self._eligible(capability, region):
            skip = await self._gate(adapter)
            if skip:
                log.info("provider_skipped", provider=adapter.name, reason=skip)
                tried.append(f"{adapter.name} ({skip})")
                continue
            try:
                return await self._invoke(adapter, method, kwargs), adapter.name
            except NotSupported:
                continue
            except Exception as exc:
                tried.append(f"{adapter.name} ({exc})")
        raise DataUnavailable(capability.value, tried)

    async def call_all(self, capability: Capability, region: Region,
                       method: str, **kwargs: Any) -> list[tuple[Any, str]]:
        """Fan out to every eligible provider in parallel; return all successes."""
        eligible = []
        for adapter in self._eligible(capability, region):
            if await self._gate(adapter) is None:
                eligible.append(adapter)
        results = await asyncio.gather(
            *(self._invoke(a, method, kwargs) for a in eligible),
            return_exceptions=True,
        )
        out: list[tuple[Any, str]] = []
        for adapter, result in zip(eligible, results, strict=True):
            if not isinstance(result, BaseException):
                out.append((result, adapter.name))
        return out

    async def health(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": a.name,
                "capabilities": sorted(c.value for c in a.capabilities),
                "breaker": await self.control.breaker_state(a.name),
                "rate_limit": {"per_minute": a.rate_limit.per_minute,
                               "per_day": a.rate_limit.per_day},
            }
            for a in self.adapters.values()
        ]
