# Equity Research & Valuation Platform — Backend

Institutional-grade equity research backend: multi-source data ingestion with fallback
chains, a fully auditable financial modeling engine, 20+ valuation models, a quant/risk
engine, and a multi-agent AI analysis pipeline.

**Scope:** backend only (API, financial engine, AI pipeline, database, ingestion,
business logic). The frontend is built separately and consumes the REST API.

## Stack

| Layer         | Technology                                          |
|---------------|-----------------------------------------------------|
| API           | Python 3.12, FastAPI (async), Pydantic v2           |
| Persistence   | PostgreSQL 16, SQLAlchemy 2.0 (async), Alembic      |
| Cache/Queue   | Redis 7 (cache, rate-limit buckets, Celery broker)  |
| Workers       | Celery (ingestion, LLM analysis, quant jobs)        |
| LLM           | OpenRouter gateway (Claude et al.), structured JSON |
| Packaging     | Docker / docker-compose, uv                         |
| Observability | structlog (JSON logs), Prometheus metrics           |

## Design documents

| Doc | Contents |
|-----|----------|
| [docs/01-architecture.md](docs/01-architecture.md) | System architecture, layers, folder structure, cross-cutting concerns |
| [docs/02-data-sources.md](docs/02-data-sources.md) | Provider adapters, fallback chains, entity resolution, rate limiting |
| [docs/03-database.md](docs/03-database.md) | Full PostgreSQL schema |
| [docs/04-api.md](docs/04-api.md) | Versioned REST API routes (OpenAPI/Swagger) |
| [docs/05-financial-engine.md](docs/05-financial-engine.md) | Auditable calculation framework, valuation models, ratios, scores, quant |
| [docs/06-ai-pipeline.md](docs/06-ai-pipeline.md) | AI agents, news engine, LLM integration |
| [docs/07-roadmap.md](docs/07-roadmap.md) | Phased implementation plan |

## Non-negotiable principles

1. **No single point of data failure** — every data class has a fallback chain of
   providers; provenance is stored with every datum.
2. **Every number is reproducible** — valuations return a full calculation trace:
   formula → substituted values → intermediates → result, plus assumptions, data
   sources, and confidence.
3. **No placeholder logic** — a model that cannot be computed for a company (e.g. DDM
   for a non-dividend payer) returns an explicit, typed "not applicable" result with
   the reason, never a fake number.
4. **Secrets live in the environment** — copy `.env.example` to `.env` and fill in
   keys. Nothing secret is ever committed.
