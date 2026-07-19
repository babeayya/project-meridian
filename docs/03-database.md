# 03 — Database Schema (PostgreSQL 16)

Conventions: UUID v7 PKs; `created_at`/`updated_at` on every table; monetary values
`NUMERIC(20,4)` in the **statement's reporting currency** with currency stored
alongside; all fetched data carries provenance columns
(`source TEXT, source_url TEXT, fetched_at TIMESTAMPTZ, batch_id UUID`).
Migrations via Alembic. Extensions: `pg_trgm` (fuzzy search), optional `pgvector`
(filing embeddings, phase 8).

## 1. Identity & reference

```sql
companies (
  id UUID PK,
  name TEXT NOT NULL,
  legal_name TEXT,
  country CHAR(2) NOT NULL,             -- ISO 3166
  cik TEXT UNIQUE,                      -- SEC (US)
  isin TEXT UNIQUE,
  lei  TEXT,
  sector TEXT, industry TEXT,           -- normalized GICS-like taxonomy
  website TEXT, ir_url TEXT,            -- IR page for filings fallback
  description TEXT,
  employees INT,
  fiscal_year_end SMALLINT,             -- month 1-12
  reporting_currency CHAR(3),
  is_active BOOL DEFAULT TRUE
)
-- INDEX gin (name gin_trgm_ops)

company_aliases (id, company_id FK, alias TEXT, source TEXT)
-- "TCS" → Tata Consultancy Services; GIN trgm index

listings (
  id UUID PK, company_id FK,
  ticker TEXT NOT NULL,                 -- "AAPL", "RELIANCE"
  exchange TEXT NOT NULL,               -- "NASDAQ", "NSE", "BSE"
  mic CHAR(4),                          -- ISO 10383
  yahoo_symbol TEXT,                    -- "RELIANCE.NS" (provider symbol map)
  currency CHAR(3) NOT NULL,
  is_primary BOOL DEFAULT FALSE,
  UNIQUE (ticker, exchange)
)

provider_symbols (listing_id FK, provider TEXT, symbol TEXT,
                  UNIQUE(provider, listing_id))

peers (company_id FK, peer_company_id FK, rank SMALLINT,
       method TEXT,                     -- 'fmp' | 'finnhub' | 'industry_screen'
       PRIMARY KEY (company_id, peer_company_id))
```

## 2. Market data

```sql
prices_daily (
  listing_id FK, date DATE,
  open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC,
  adj_close NUMERIC, volume BIGINT,
  source TEXT, batch_id UUID,
  PRIMARY KEY (listing_id, date)
) PARTITION BY RANGE (date);            -- yearly partitions

quotes_latest (listing_id PK, price NUMERIC, change_pct NUMERIC,
               market_cap NUMERIC, volume BIGINT, as_of TIMESTAMPTZ, source TEXT)

fx_rates (base CHAR(3), quote CHAR(3), date DATE, rate NUMERIC,
          source TEXT, PRIMARY KEY (base, quote, date))
```

## 3. Fundamentals

Statements are stored **normalized to a canonical taxonomy** (auditable, queryable)
*plus* the raw provider payload (reproducible, re-mappable).

```sql
financial_statements (
  id UUID PK, company_id FK,
  statement_type TEXT CHECK (IN ('income','balance','cashflow')),
  period_type   TEXT CHECK (IN ('annual','quarterly','ttm')),
  fiscal_year SMALLINT, fiscal_period TEXT,      -- 'FY','Q1'..'Q4'
  period_start DATE, period_end DATE NOT NULL,
  currency CHAR(3) NOT NULL, scale_hint TEXT,    -- as-reported scale detected
  filed_at DATE, restated BOOL DEFAULT FALSE,
  source TEXT, source_url TEXT, fetched_at TIMESTAMPTZ, batch_id UUID,
  raw JSONB NOT NULL,                            -- untouched provider payload
  UNIQUE (company_id, statement_type, period_type, period_end, source)
)

financial_line_items (
  statement_id FK, key TEXT,             -- canonical key: 'revenue','ebit',
                                         -- 'capex','dso'… (domain/statements/taxonomy.py)
  label_as_reported TEXT,
  value NUMERIC(20,4),
  PRIMARY KEY (statement_id, key)
)

data_quality_flags (
  id UUID PK, company_id FK, scope TEXT,          -- 'statement','price','ownership'
  ref_id UUID, severity TEXT,                     -- 'info','warn','error'
  code TEXT,                                      -- 'CROSS_SOURCE_DELTA','BS_IMBALANCE'
  detail JSONB, created_at TIMESTAMPTZ
)
```

## 4. Corporate actions, ownership, estimates

```sql
dividends   (id, company_id FK, ex_date DATE, pay_date DATE, amount NUMERIC,
             currency CHAR(3), type TEXT, source TEXT,
             UNIQUE(company_id, ex_date, amount))
splits      (id, company_id FK, ex_date DATE, numerator NUMERIC,
             denominator NUMERIC, source TEXT)
buybacks    (id, company_id FK, period_end DATE, amount NUMERIC, currency CHAR(3),
             shares_repurchased NUMERIC, method TEXT, source TEXT)

institutional_holdings (
  id, company_id FK, holder_name TEXT, holder_cik TEXT,
  report_date DATE, shares NUMERIC, value NUMERIC, pct_out NUMERIC,
  change_shares NUMERIC, source TEXT)

insider_transactions (
  id, company_id FK, insider_name TEXT, relation TEXT,
  transaction_date DATE, type TEXT,     -- 'buy','sell','award','exercise'
  shares NUMERIC, price NUMERIC, value NUMERIC, source TEXT)

shareholding_pattern (                  -- India quarterly disclosure
  id, company_id FK, as_of DATE,
  promoter_pct NUMERIC, promoter_pledged_pct NUMERIC,
  fii_pct NUMERIC, dii_pct NUMERIC, public_pct NUMERIC, source TEXT,
  UNIQUE(company_id, as_of))

analyst_estimates (
  id, company_id FK, as_of DATE, fiscal_year SMALLINT, fiscal_period TEXT,
  metric TEXT,                          -- 'revenue','eps','ebitda'
  mean NUMERIC, median NUMERIC, high NUMERIC, low NUMERIC,
  num_analysts SMALLINT, source TEXT)

management_guidance (
  id, company_id FK, given_at DATE, fiscal_year SMALLINT, fiscal_period TEXT,
  metric TEXT, low NUMERIC, high NUMERIC, unit TEXT,
  verbatim TEXT,                        -- exact quote
  source_doc_id UUID,                   -- FK → filings/transcripts
  extraction_confidence NUMERIC)        -- LLM-extracted (06)
```

## 5. Filings & documents

```sql
filings (
  id UUID PK, company_id FK,
  filing_type TEXT,                     -- '10-K','10-Q','8-K','DEF 14A',
                                        -- 'annual_report','transcript','press_release'
  period_end DATE, filed_at DATE, title TEXT,
  url TEXT NOT NULL, local_path TEXT,   -- fetched artifact (object storage/disk)
  word_count INT, source TEXT,
  UNIQUE(company_id, filing_type, url))

document_chunks (                       -- phase 8, pgvector
  id UUID PK, filing_id FK, seq INT, section TEXT, text TEXT,
  embedding vector(1024))
```

## 6. Macro

```sql
macro_series (
  code TEXT PRIMARY KEY,                -- 'US10Y','IN_CPI_YOY','WTI', ...
  name TEXT, unit TEXT, country CHAR(2), source TEXT, source_code TEXT,
  frequency TEXT)

macro_observations (
  series_code FK, date DATE, value NUMERIC, fetched_at TIMESTAMPTZ,
  PRIMARY KEY (series_code, date))
```

## 7. Valuation & assumptions (the audit core)

```sql
assumption_sets (
  id UUID PK, company_id FK,
  name TEXT,                            -- 'base','bull','bear','user:<label>'
  based_on UUID,                        -- parent set (override lineage)
  assumptions JSONB NOT NULL,           -- typed via Pydantic AssumptionSet schema:
                                        --  revenue_growth[], margin paths, capex/sales,
                                        --  nwc drivers, tax rate, wacc inputs,
                                        --  terminal_growth, exit_multiple, forecast_years,
                                        --  buyback %, dilution %, debt schedule
  derivation JSONB,                     -- how each default was derived (source + method)
  created_by TEXT, created_at TIMESTAMPTZ)

data_snapshots (                        -- reproducibility: freeze model inputs
  id UUID PK, company_id FK, created_at TIMESTAMPTZ,
  inputs JSONB NOT NULL)                -- statement ids, price date, macro values used

valuation_runs (
  id UUID PK, company_id FK,
  model TEXT NOT NULL,                  -- 'dcf_fcff','dcf_fcfe','ddm','residual_income',
                                        -- 'eva','comps','precedent','asset_based','sotp',
                                        -- 'reverse_dcf','monte_carlo_dcf','expected_return',
                                        -- 'multiples','scenario','summary'
  assumption_set_id FK, snapshot_id FK,
  status TEXT,                          -- 'ok','not_applicable','failed'
  not_applicable_reason TEXT,
  fair_value_per_share NUMERIC, currency CHAR(3),
  upside_pct NUMERIC, price_at_run NUMERIC,
  low NUMERIC, high NUMERIC,            -- intrinsic value range
  confidence NUMERIC,
  outputs JSONB NOT NULL,               -- model-specific results
  trace JSONB NOT NULL,                 -- full CalcNode tree (05) — every formula,
                                        -- substitution, intermediate, source
  engine_version TEXT NOT NULL,         -- code version for reproducibility
  created_at TIMESTAMPTZ)
-- INDEX (company_id, model, created_at DESC)
```

## 8. Scores, ratios, quant

```sql
ratio_snapshots (
  id, company_id FK, as_of DATE, period_type TEXT,
  ratios JSONB NOT NULL,                -- {key: {value, formula, inputs, trace_ref}}
  UNIQUE(company_id, as_of, period_type))

score_snapshots (
  id, company_id FK, as_of DATE,
  score_type TEXT,                      -- 'altman_z','piotroski_f','beneish_m','dupont',
                                        -- 'quality','growth','momentum','value',
                                        -- 'profitability','risk','composite'
  value NUMERIC, grade TEXT, components JSONB, trace JSONB,
  UNIQUE(company_id, as_of, score_type))

quant_snapshots (
  id, company_id FK, as_of DATE, window TEXT,     -- '1y','3y','5y'
  metrics JSONB,                        -- beta, alpha, sharpe, sortino, treynor, IR,
                                        -- TE, VaR/CVaR levels, factor loadings
  benchmark TEXT, trace JSONB,
  UNIQUE(company_id, as_of, window, benchmark))
```

## 9. News & AI

```sql
news_articles (
  id UUID PK, company_id FK NULL,       -- NULL = macro/sector news
  url TEXT UNIQUE, url_hash TEXT UNIQUE,
  headline TEXT, summary TEXT, body TEXT,
  outlet TEXT, author TEXT, published_at TIMESTAMPTZ,
  language CHAR(2), category TEXT,      -- 'breaking','earnings','mna','regulatory',...
  provider TEXT)                        -- 'newsapi','gdelt','yahoo'

news_analysis (
  article_id PK FK,
  sentiment TEXT CHECK (IN ('positive','neutral','negative')),
  sentiment_score NUMERIC,              -- -1..1
  confidence NUMERIC, importance NUMERIC,          -- 0..1
  expected_impact TEXT,                 -- LLM: direction+magnitude rationale
  affected_segments TEXT[],
  model TEXT, prompt_version TEXT, analyzed_at TIMESTAMPTZ)

ai_analyses (
  id UUID PK, company_id FK,
  agent TEXT NOT NULL,                  -- 'news','financial_statement','macro','industry',
                                        -- 'management','competitive','valuation','risk',
                                        -- 'moat','red_flag','fraud','esg','thesis'
  output JSONB NOT NULL,                -- validated against agent's Pydantic schema
  model TEXT, prompt_version TEXT,
  input_refs JSONB,                     -- ids of statements/news/filings consumed
  tokens_in INT, tokens_out INT, cost_usd NUMERIC,
  confidence NUMERIC, created_at TIMESTAMPTZ)
-- INDEX (company_id, agent, created_at DESC)
```

## 10. Operations

```sql
provider_call_log (id, provider TEXT, endpoint TEXT, listing_id FK NULL,
                   status SMALLINT, ok BOOL, latency_ms INT,
                   error TEXT, called_at TIMESTAMPTZ)
provider_budgets  (provider PK, daily_limit INT, used_today INT, resets_at TIMESTAMPTZ)
ingestion_batches (id UUID PK, company_id FK, plan JSONB, status TEXT,
                   started_at, finished_at, stats JSONB)
task_results      (task_id PK, kind TEXT, status TEXT, result_ref JSONB,
                   error TEXT, created_at, finished_at)
```
