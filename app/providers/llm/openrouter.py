"""OpenRouter LLM gateway client with structured-output enforcement.

Every call: schema-in-prompt + JSON validation against a Pydantic model; on
validation failure, ONE repair round-trip with the errors; second failure
raises (invalid output is never stored). Usage/cost recorded per call.
"""
import json
from typing import TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

log = structlog.get_logger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TransportError):
        return True
    return (isinstance(exc, httpx.HTTPStatusError)
            and exc.response.status_code in RETRYABLE_STATUS)

BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

T = TypeVar("T", bound=BaseModel)


class LlmNotConfigured(Exception):
    pass


class LlmUsage(BaseModel):
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


class LlmResult[T]:
    def __init__(self, output: T, usage: LlmUsage, raw_text: str) -> None:
        self.output = output
        self.usage = usage
        self.raw_text = raw_text


class OpenRouterClient:
    def __init__(self, http_raw: httpx.AsyncClient, api_key: str,
                 default_model: str) -> None:
        if not api_key:
            raise LlmNotConfigured("OPENROUTER_API_KEY is not set")
        self._http = http_raw
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "Equity Research Platform",
        }
        self.default_model = default_model

    async def _chat(self, model: str, messages: list[dict]) -> tuple[str, LlmUsage]:
        # retry transient failures — free-tier model pools 429 briefly under load
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential_jitter(initial=1.5, max=20.0),
            retry=retry_if_exception(_retryable),
            reraise=True,
        ):
            with attempt:
                # NOTE: no response_format param — several upstream providers
                # 400 on it; JSON is enforced by schema-in-prompt + extraction
                # + one repair round-trip instead (maximum model compatibility).
                resp = await self._http.post(
                    BASE_URL, headers=self._headers, timeout=120.0,
                    json={"model": model, "messages": messages,
                          # explicit cap: without it OpenRouter reserves
                          # worst-case cost and 402s low-credit accounts
                          "max_tokens": 6000, "temperature": 0.2},
                )
                resp.raise_for_status()
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"OpenRouter error: {str(data)[:300]}")
        text = data["choices"][0]["message"]["content"] or ""
        usage = data.get("usage", {})
        return text, LlmUsage(model=data.get("model", model),
                              tokens_in=usage.get("prompt_tokens", 0),
                              tokens_out=usage.get("completion_tokens", 0))

    @staticmethod
    def _extract_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.removeprefix("json").strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise json.JSONDecodeError("no JSON object found", text, 0)
        return json.loads(text[start:end + 1])

    async def structured(self, schema: type[T], system: str, user: str,
                         model: str | None = None) -> LlmResult[T]:
        model = model or self.default_model
        schema_json = json.dumps(schema.model_json_schema(), indent=None)
        messages = [
            {"role": "system", "content":
                f"{system}\n\nRespond with ONLY a JSON object that validates "
                f"against this JSON Schema:\n{schema_json}\n"
                "No prose outside the JSON. Use null for unknown values. "
                "If the provided data is insufficient for a field, say so inside "
                "the relevant string field rather than inventing figures."},
            {"role": "user", "content": user},
        ]
        text, usage = await self._chat(model, messages)
        try:
            return LlmResult(schema.model_validate(self._extract_json(text)), usage, text)
        except (ValidationError, json.JSONDecodeError) as exc:
            log.warning("llm_schema_repair", model=model, error=str(exc)[:300])
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content":
                             f"Your JSON failed validation:\n{str(exc)[:1500]}\n"
                             "Return the corrected JSON object only."})
            text2, usage2 = await self._chat(model, messages)
            usage.tokens_in += usage2.tokens_in
            usage.tokens_out += usage2.tokens_out
            return LlmResult(schema.model_validate(self._extract_json(text2)),
                             usage, text2)
