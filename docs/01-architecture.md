# 01 — System Architecture

## 1. High-level architecture

```
                        ┌─────────────────────────────────────────────┐
                        │                  Frontend                   │
                        │            (separate project)               │
                        └──────────────────┬──────────────────────────┘
                                           │ HTTPS / JSON
                        ┌──────────────────▼──────────────────────────┐
                        │           FastAPI (async, /api/v1)          │
                        │  routers → services → repositories → DB     │
                        │  OpenAPI/Swagger, auth, rate limit, CORS    │
                        └───────┬──────────────────────┬──────────────┘
                                │                      │ enqueue
                    ┌───────────▼───────────┐   ┌──────▼───────────────┐
                    │      PostgreSQL       │   │    Celery workers    │
                    │  canonical store +    │   │  q: ingestion        │
                    │  valuation runs +     │   │  q: analysis (LLM)   │
                    │  AI outputs + news    │   │  q: quant            │
                    └───────────▲───────────┘   │  q: news             │
                                │               └──────┬───────────────┘
                    ┌───────────┴───────────┐          │
                    │        Redis          │◄─────────┤ broker/results
                    │ cache · rate buckets  │          │
                    │ circuit-breaker state │   ┌──────▼───────────────┐
                    └───────────────────────┘   │  Provider adapters   │
                                                │  Yahoo, AlphaVantage,│
                                                │  FMP, Finnhub, EDGAR,│
                                                │  Stooq, FRED, NSE/BSE│
                                                │  NewsAPI, GDELT, ... │
                                                │  + OpenRouter (LLM)  │
                                                └──────────────────────┘
```

Request flow for "analyze NVIDIA":

1. `POST /api/v1/companies/resolve {"query": "NVIDIA"}` → entity resolution
   (local DB first, then provider symbol search) → canonical `company_id`.
2. `POST /api/v1/companies/{id}/refresh` → Celery fans out ingestion tasks per data
   class (prices, statements, ownership, actions, estimates, news, macro context).
   Each task walks its provider fallback chain and normalizes into PostgreSQL.
3. Sync reads (`GET /financials`, `GET /ratios`, …) are served from PostgreSQL with a
   Redis read-through cache. If data is stale/missing, the API returns what it has
   with `freshness` metadata and (optionally) triggers a background refresh.
4. Valuations (`POST /valuations/{id}/dcf`) run synchronously when inputs are cached
   (pure computation, <1s) and return a full audit trace; Monte Carlo and multi-agent
   AI analysis run as Celery jobs with a `task_id` to poll.

## 2. Layered design (strict, one-way dependencies)

```
api (routers, request/response schemas)
  └─► services (business orchestration, fallback policy, valuation orchestration)
        ├─► domain (pure logic: financial engine, quant, scores — NO I/O)
        ├─► repositories (SQLAlchemy persistence, one per aggregate)
        └─► providers (external I/O: HTTP clients per data vendor, LLM gateway)
core (config, logging, errors, DI container, redis, http) ← usable by every layer
```

Rules:

- `domain/` is **pure**: functions take Pydantic value objects in, return value
  objects (with calculation traces) out. No DB, no HTTP, no clock reads (time is a
  parameter). This makes every valuation unit-testable and reproducible.
- `providers/` never touch the DB; they return normalized Pydantic DTOs.
- `repositories/` are the only layer that imports SQLAlchemy models.
- `services/` compose the above; Celery tasks are thin wrappers around services.
- Dependency injection via FastAPI `Depends` + a small container in
  `core/container.py` (providers, repos, and services are constructor-injected so
  tests can swap fakes).

## 3. Folder structure

```
backend/
├── pyproject.toml                  # uv-managed; ruff, mypy, pytest config
├── alembic.ini
├── docker-compose.yml              # api, worker, beat, postgres, redis
├── Dockerfile
├── .env.example
├── alembic/
│   └── versions/
├── app/
│   ├── main.py                     # FastAPI app factory, lifespan, middleware
│   ├── core/
│   │   ├── config.py               # pydantic-settings; ALL keys from env
│   │   ├── logging.py              # structlog JSON config, request-id binding
│   │   ├── errors.py               # error taxonomy → RFC7807 problem responses
│   │   ├── container.py            # DI wiring
│   │   ├── database.py             # async engine/session factory
│   │   ├── redis.py                # redis pool
│   │   ├── http.py                 # shared httpx.AsyncClient, retry (tenacity),
│   │   │                           #   per-provider token-bucket rate limiter,
│   │   │                           #   circuit breaker
│   │   └── security.py             # API-key auth for the frontend, CORS
│   ├── models/                     # SQLAlchemy ORM models (see 03-database.md)
│   │   ├── company.py  listing.py  price.py  fundamentals.py
│   │   ├── ownership.py  actions.py  estimates.py  macro.py
│   │   ├── news.py  valuation.py  ai.py  scores.py  provider_log.py
│   ├── schemas/                    # Pydantic DTOs (api + provider-normalized)
│   │   ├── common.py               # Money, Provenance, Freshness, CalcTrace
│   │   ├── company.py  prices.py  fundamentals.py  valuation.py
│   │   ├── assumptions.py  scores.py  quant.py  news.py  ai.py  charts.py
│   ├── providers/
│   │   ├── base.py                 # ProviderAdapter ABC + capability enum
│   │   ├── registry.py             # capability → ordered fallback chain
│   │   ├── yahoo.py  alpha_vantage.py  fmp.py  finnhub.py  polygon.py
│   │   ├── sec_edgar.py            # companyfacts + filings index (XBRL)
│   │   ├── nse.py  bse.py          # Indian market adapters
│   │   ├── stooq.py  macrotrends.py
│   │   ├── fred.py  world_bank.py  trading_economics.py
│   │   ├── newsapi.py  gdelt.py
│   │   └── llm/
│   │       ├── openrouter.py       # chat + structured-output client
│   │       └── schema_repair.py    # re-ask on invalid JSON
│   ├── repositories/
│   │   ├── base.py  company.py  prices.py  fundamentals.py
│   │   ├── ownership.py  actions.py  estimates.py  macro.py
│   │   ├── news.py  valuation.py  ai.py  scores.py
│   ├── services/
│   │   ├── resolution.py           # name/ticker → company (search + dedupe)
│   │   ├── ingestion/              # one service per data class, owns its chain
│   │   │   ├── prices.py  fundamentals.py  ownership.py  actions.py
│   │   │   ├── estimates.py  macro.py  peers.py  filings.py
│   │   ├── financials.py           # canonical statement assembly, TTM, CAGR
│   │   ├── ratios.py  scores.py
│   │   ├── valuation/
│   │   │   ├── orchestrator.py     # run/save/load valuation runs + snapshots
│   │   │   ├── assumptions.py      # default assumption builder + user overrides
│   │   │   ├── wacc.py             # cost of capital service (macro inputs)
│   │   │   └── summary.py          # football field, prob-weighted value, MoS
│   │   ├── quant.py
│   │   ├── news.py                 # fetch, dedupe, classify pipeline
│   │   ├── ai/
│   │   │   ├── orchestrator.py     # agent fan-out, dependency graph
│   │   │   ├── context.py          # builds per-agent context packs from DB
│   │   │   └── agents/             # one module per agent (see 06-ai-pipeline.md)
│   │   └── charts.py               # shapes engine output for visualization APIs
│   ├── domain/                     # PURE — no I/O anywhere below
│   │   ├── calc/
│   │   │   ├── trace.py            # CalcNode: formula/inputs/substitution/result
│   │   │   └── units.py            # currency & scale safety (mn vs bn, INR vs USD)
│   │   ├── statements/
│   │   │   ├── taxonomy.py         # canonical line-item keys + synonyms mapping
│   │   │   └── derived.py          # EBITDA, NOPAT, FCFF/FCFE, invested capital
│   │   ├── forecast/
│   │   │   ├── drivers.py          # revenue/margin/capex/NWC driver models
│   │   │   ├── debt_schedule.py    # revolver, amortization, interest
│   │   │   └── share_count.py      # buybacks, dilution
│   │   ├── valuation/
│   │   │   ├── dcf.py              # FCFF & FCFE, terminal (Gordon + exit multiple)
│   │   │   ├── ddm.py  residual_income.py  eva.py  asset_based.py
│   │   │   ├── comps.py  precedent.py  sotp.py
│   │   │   ├── reverse_dcf.py  expected_return.py
│   │   │   ├── monte_carlo.py  sensitivity.py  scenarios.py
│   │   │   └── multiples.py        # EV/EBITDA, EV/S, P/E, PEG, P/B, P/CF
│   │   ├── ratios/
│   │   │   ├── profitability.py  liquidity.py  leverage.py  efficiency.py
│   │   │   ├── dupont.py
│   │   ├── scores/
│   │   │   ├── altman.py  piotroski.py  beneish.py
│   │   │   └── composite.py        # quality/growth/value/momentum/risk/composite
│   │   └── quant/
│   │       ├── returns.py  capm.py  fama_french.py
│   │       ├── risk.py             # VaR, CVaR/ES, drawdown
│   │       ├── performance.py      # Sharpe, Sortino, Treynor, Jensen, IR, TE
│   │       └── correlation.py
│   ├── api/
│   │   └── v1/
│   │       ├── router.py           # aggregates sub-routers
│   │       ├── companies.py  prices.py  financials.py  ratios.py
│   │       ├── valuations.py  assumptions.py  scores.py  quant.py
│   │       ├── news.py  ai.py  macro.py  charts.py  tasks.py  health.py
│   ├── workers/
│   │   ├── celery_app.py           # queues, routing, beat schedule
│   │   └── tasks/
│   │       ├── ingestion.py  analysis.py  quant.py  news.py  maintenance.py
│   └── __init__.py
└── tests/
    ├── unit/                       # domain/ — golden-number tests, no I/O
    ├── integration/                # repos vs. real Postgres (testcontainers)
    ├── contract/                   # provider adapters vs. recorded fixtures (vcr)
    └── api/                        # httpx.AsyncClient against app with fakes
```

## 4. Cross-cutting concerns

### Configuration
`pydantic-settings` class in `core/config.py`. Every provider key is optional — the
registry only enables adapters whose keys are present (Yahoo, Stooq, EDGAR, GDELT,
World Bank, FRED-public need no key). Missing-key providers are skipped in fallback
chains, never crash.

### Resilience (per external call)
- **Retry:** tenacity — exponential backoff + jitter, max 3 attempts, retry only on
  429/5xx/timeouts; never on 4xx business errors.
- **Rate limiting:** Redis token bucket per provider (e.g. Alpha Vantage 5/min,
  25/day free tier) enforced *before* the call; budget exhaustion → skip to next
  provider in chain, log a `provider_skipped` event.
- **Circuit breaker:** per provider in Redis; opens after N consecutive failures,
  half-opens after cooldown. Open circuit → immediate fallback.
- **Timeouts:** connect 5s / read 15s defaults; LLM calls 120s.

### Caching (Redis, read-through)
| Data class | TTL |
|---|---|
| Intraday quote | 5 min |
| Daily OHLCV (historical) | 24 h |
| Financial statements | 24 h (invalidated on new-filing detection) |
| Ratios/scores (derived) | invalidated with their inputs |
| Macro series | 24 h |
| News list | 10 min |
| Entity resolution | 7 d |
| LLM agent outputs | persisted in Postgres; re-run on demand or on new filings |

Cache keys are versioned (`v1:prices:{security_id}:{range}`) so schema changes never
serve stale shapes.

### Error taxonomy
`AppError` hierarchy → RFC 7807 `application/problem+json`:
`EntityNotResolved`, `DataUnavailable(data_class, providers_tried)`,
`ModelNotApplicable(model, reason)`, `ProviderQuotaExceeded`, `StaleDataWarning`
(non-fatal, embedded in response `meta`), `ValidationError`.

### Logging & observability
- structlog JSON: every log line carries `request_id`, `company_id`, `provider`,
  `task_id` where relevant.
- Every provider call logged to `provider_call_log` table (provider, endpoint,
  status, latency, credits used) — this powers `/health/providers` and quota
  planning.
- Prometheus counters: provider success/failure/fallback-depth, cache hit ratio,
  valuation runs, LLM tokens.

### Testing strategy
- **Unit (domain):** golden-number tests — hand-computed DCF/WACC/Z-score fixtures
  (e.g. a fully worked AAPL FY2023 DCF checked against a spreadsheet) must match to
  the cent. Property tests (hypothesis) for invariants (e.g. FCFF identity, PV
  monotonic in discount rate).
- **Contract (providers):** recorded HTTP cassettes (vcrpy) so adapter parsing is
  tested offline; a nightly "live smoke" job validates cassettes haven't drifted.
- **Integration (repos):** testcontainers-python spins real Postgres.
- **API:** full request→response tests with provider fakes injected via DI.

### Security
- All secrets from env; `.env` git-ignored; `.env.example` documents names only.
- Frontend authenticates with an API key header (`X-API-Key`) initially; JWT later.
- SQL injection impossible by construction (SQLAlchemy bound params); outbound URLs
  are allow-listed per adapter (no user-controlled URL fetches).
- LLM outputs are data, never executed; prompt-injection-resistant context building
  (news/filings text is delimited and tagged as untrusted).
