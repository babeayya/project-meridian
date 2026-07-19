# 07 — Implementation Roadmap

Phases are vertical slices — each ends with working, tested endpoints. Order chosen
so the auditable financial core exists before AI polish.

> **Status (2026-07-10):** Phases 0–8 implemented and live-verified (AAPL via
> SEC EDGAR + RELIANCE.NS via Yahoo, full valuation suite, quant, news, AI agent
> framework). Remaining backlog from the original spec: FMP/Finnhub/Polygon
> adapters activate when keys are added; institutional ownership/insider/13F,
> analyst estimates, filings full-text + transcripts, peer auto-discovery for
> cross-company comps, SOTP/precedent-transactions (return typed
> `not_applicable` until segment/deal data is ingested), Celery beat schedules,
> Alembic baseline migration, Fama-French factor loadings. AI agents require
> `OPENROUTER_API_KEY`; news classification degrades to a lexicon heuristic
> without it.

## Phase 0 — Foundation (scaffold)
- Repo layout, `pyproject.toml` (uv), ruff + mypy + pytest config.
- `core/`: config (pydantic-settings), structlog JSON logging, error taxonomy,
  async SQLAlchemy engine, Redis pool, shared httpx client with tenacity retry,
  token-bucket rate limiter, circuit breaker.
- Docker compose: api + worker + beat + postgres + redis. Alembic baseline.
- `/health`, `/health/ready`. CI-ready test harness.
- **Exit test:** `docker compose up` → green health checks; unit tests pass.

## Phase 1 — Identity & prices
- Tables: companies, aliases, listings, provider_symbols, prices_daily, quotes.
- Seed sync: SEC company_tickers.json + NSE/BSE master lists.
- Adapters: Yahoo, Stooq, Alpha Vantage (search + OHLCV + quote); registry +
  fallback executor + provider_call_log + budgets.
- `POST /companies/resolve`, `GET /companies/{id}`, `/prices`, `/quote`,
  `/health/providers`. Celery ingestion queue live.
- **Exit test:** type "Apple", "TCS", "Reliance" → resolved with 5y prices, with
  Yahoo blocked → Stooq serves.

## Phase 2 — Fundamentals
- Tables: financial_statements, line_items, data_quality_flags, actions, ownership,
  estimates, filings. Canonical taxonomy + synonym mapper + unit/scale detection.
- Adapters: SEC EDGAR (companyfacts XBRL + filings index), FMP, yfinance
  fundamentals, Finnhub; NSE/BSE actions + shareholding.
- Validation gates + cross-source reconciliation. Refresh orchestration (chord).
- Endpoints: `/financials`, `/dividends`, `/ownership`, `/estimates`, `/filings`,
  `/peers`, `/freshness`, `/refresh`, `/tasks/{id}`.
- **Exit test:** AAPL 10y annual + 8q quarterly from EDGAR; RELIANCE.NS from
  Yahoo/FMP chain; balance sheets balance; provenance on every statement.

## Phase 3 — Ratios, derived metrics & scores
- `domain/calc` CalcNode framework + units. `domain/statements/derived.py`.
- Full ratio engine + DuPont; Altman/Piotroski/Beneish; composite factor scores.
- Endpoints: `/ratios`, `/ratios/dupont`, `/scores/*`, `/charts/margins`,
  `/charts/ratio-history`, `/charts/financial-history`.
- **Exit test:** golden-number fixtures (hand-built spreadsheet parity) to the cent.

## Phase 4 — Valuation core
- Macro adapters (FRED, World Bank) + `/macro/*`; WACC service.
- Assumption sets (default derivation + overrides API), data snapshots.
- Forecast engine (drivers, debt schedule with circularity solver, share walk).
- DCF FCFF/FCFE + Gordon/exit-multiple terminal; multiples; comps.
- Endpoints: `/assumptions*`, `/valuations/dcf-*`, `/valuations/comps`,
  `/valuations/runs/{id}` with full trace; `/charts/dcf-waterfall`, `/forecast`.
- **Exit test:** stored run re-executes bit-identically from its snapshot; trace
  renders formula → substitution → result for every node.

## Phase 5 — Full valuation suite
- DDM, residual income, EVA (with DCF consistency assertion), asset-based, SOTP,
  precedent transactions, reverse DCF, expected return.
- Sensitivity, scenarios + probability weighting + margin of safety, Monte Carlo
  DCF (seeded), summary/football field.
- Charts: sensitivity-matrix, monte-carlo-distribution, valuation-bridge.
- **Exit test:** non-applicable models return typed reasons (DDM on a
  non-payer); bank auto-routes to RI/DDM; MC reproducible by seed.

## Phase 6 — Quant engine
- Returns/beta/factor models, performance ratios, VaR/CVaR, correlations, rolling
  series, GBM simulation. Endpoints `/quant/*` + benchmark auto-selection.
- **Exit test:** metrics match reference library values on fixture data within 1e-8.

## Phase 7 — News engine
- NewsAPI + GDELT + Yahoo news adapters; dedupe; batched LLM classification;
  sentiment timeline; breaking flag; polling schedule.
- Endpoints `/news*`, `/news/sentiment-timeline`.
- **Exit test:** 30d TSLA news classified; duplicate wire stories collapse to one.

## Phase 8 — AI agents
- OpenRouter client + schema-repair; prompt registry; context builders;
  12 agents + thesis synthesizer DAG; guidance extraction from transcripts;
  optional pgvector filing chunks for retrieval.
- Endpoints `/ai/*`; `/charts/risk-heatmap`, `/charts/radar-scores`.
- **Exit test:** full agent run on NVDA produces schema-valid JSON for every agent;
  thesis cites agent evidence keys; cost per full run logged.

## Phase 9 — Hardening & release
- Load tests; quota-exhaustion chaos tests (kill providers, verify chains);
  security pass (authz, injection fences); OpenAPI polish + examples;
  Grafana-ready metrics; README runbooks; backup/retention policy.

## Definition of done (every phase)
Unit + integration + API tests green · mypy/ruff clean · no TODO/placeholder logic ·
every computed number traceable · every fetched datum has provenance · docs updated.
