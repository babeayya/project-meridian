"""Application settings. Every secret comes from the environment / .env file."""
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = Field(default="dev", description="dev | staging | prod")
    log_level: str = "INFO"

    # Comma-separated exact frontend origins allowed by CORS in non-dev envs,
    # e.g. "https://meridian.vercel.app,https://www.example.com". In dev, all
    # origins are allowed. In prod this MUST be set or the browser blocks the
    # frontend. Set via the CORS_ORIGINS environment variable on the host.
    cors_origins: str = ""

    # Dev default is a local SQLite file so the API runs without Docker/Postgres.
    # Production (docker-compose) overrides with postgresql+asyncpg://...
    database_url: str = "sqlite+aiosqlite:///./equity_research.db"
    # 'memory://' selects the in-process control plane (no Redis needed in dev).
    redis_url: str = "memory://"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Managed Postgres hosts (Vercel Postgres, Neon, Supabase, Railway,
        Render) hand out plain postgres:// / postgresql:// URLs with a
        psycopg-style ?sslmode=require query param. Rewrite to the asyncpg
        driver and drop sslmode, which asyncpg's DBAPI doesn't understand —
        TLS is negotiated separately in database.py's connect_args."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://"):]
        if v.startswith("postgresql+asyncpg://"):
            parts = urlsplit(v)
            query = dict(parse_qsl(parts.query))
            query.pop("sslmode", None)
            query.pop("channel_binding", None)
            v = urlunsplit(parts._replace(query=urlencode(query)))
        return v

    # Comma-separated API keys the frontend may present via X-API-Key.
    # Empty ⇒ auth disabled (dev only; startup logs a warning outside dev).
    api_keys: str = ""

    # LLM gateway (AI pipeline, phase 8)
    openrouter_api_key: str = ""
    llm_model_analysis: str = "anthropic/claude-sonnet-4.5"
    llm_model_classify: str = "anthropic/claude-haiku-4.5"

    # Data providers — adapters register only when their key is present.
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""
    finnhub_api_key: str = ""
    polygon_api_key: str = ""
    fred_api_key: str = ""
    newsapi_api_key: str = ""
    sec_edgar_user_agent: str = "EquityResearchPlatform contact@example.com"

    http_connect_timeout: float = 5.0
    http_read_timeout: float = 15.0

    circuit_failure_threshold: int = 5
    circuit_cooldown_seconds: int = 300

    @property
    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
