"""Shared resilient HTTP client: retry with exponential backoff + jitter on
transient failures (429/5xx/transport errors), never on business 4xx."""
import json
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = structlog.get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


class HttpClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        attempts: int = 3,
    ) -> httpx.Response:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=0.5, max=8.0),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp
        raise AssertionError("unreachable")  # pragma: no cover

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = await self.get(url, **kwargs)
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise httpx.HTTPStatusError(
                f"Non-JSON response from {url}", request=resp.request, response=resp
            ) from exc

    async def get_text(self, url: str, **kwargs: Any) -> str:
        resp = await self.get(url, **kwargs)
        return resp.text


def build_http_client(connect_timeout: float, read_timeout: float) -> httpx.AsyncClient:
    timeout = httpx.Timeout(read_timeout, connect=connect_timeout)
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers={"Accept": "application/json, text/csv;q=0.9, */*;q=0.8"},
    )
