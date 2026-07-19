# 02 — Data Sources, Fallback Chains & Entity Resolution

## 1. Provider adapter contract

Every adapter implements a narrow ABC and declares its **capabilities**:

```python
class Capability(str, Enum):
    SYMBOL_SEARCH = "symbol_search"
    QUOTE = "quote"
    OHLCV_DAILY = "ohlcv_daily"
    OHLCV_INTRADAY = "ohlcv_intraday"
    STATEMENTS_ANNUAL = "statements_annual"
    STATEMENTS_QUARTERLY = "statements_quarterly"
    DIVIDENDS = "dividends"
    SPLITS = "splits"
    BUYBACKS = "buybacks"
    OWNERSHIP_INSTITUTIONAL = "ownership_institutional"
    OWNERSHIP_INSIDER = "ownership_insider"
    SHAREHOLDING_PATTERN = "shareholding_pattern"   # India-specific
    ESTIMATES = "estimates"
    GUIDANCE = "guidance"
    PEERS = "peers"
    FILINGS = "filings"
    TRANSCRIPTS = "transcripts"
    NEWS = "news"
    MACRO_SERIES = "macro_series"
    FX = "fx"
    COMMODITIES = "commodities"
```

```python
class ProviderAdapter(ABC):
    name: str
    capabilities: set[Capability]
    regions: set[Region]          # e.g. {US}, {IN}, {GLOBAL}
    rate_limit: RateLimit         # tokens/interval + daily budget
    requires_key: bool

    async def health(self) -> ProviderHealth: ...
    # capability-specific methods return NORMALIZED Pydantic DTOs, each datum
    # stamped with Provenance(source, source_url, fetched_at, license_note)
```

The **registry** maps `(capability, region)` → an ordered chain. Chains are config,
not code — reorderable via env/DB without redeploy.

## 2. Fallback chains (initial configuration)

| Data class | Chain (US/global) | Chain (India) |
|---|---|---|
| Symbol search | Local DB → Yahoo search → FMP search → Alpha Vantage SYMBOL_SEARCH → Finnhub | Local DB → Yahoo (.NS/.BO) → NSE master list → BSE master list |
| Quote / OHLCV daily | Yahoo → Stooq → Alpha Vantage → Finnhub → Polygon | Yahoo (.NS/.BO) → NSE bhavcopy → Stooq |
| Statements (A/Q) | SEC EDGAR companyfacts (XBRL, authoritative for US) → FMP → Yahoo/yfinance → Alpha Vantage → Macrotrends | Yahoo (.NS) → FMP → NSE/BSE filings (XBRL where available) → screener-free sources |
| Dividends/splits | Yahoo → FMP → Alpha Vantage | Yahoo → NSE corporate actions → BSE |
| Buybacks | Derived from cash-flow statement (repurchase line) → FMP | Same + SEBI/NSE announcements |
| Institutional ownership | SEC 13F via EDGAR → FMP → Finnhub | NSE/BSE shareholding pattern (quarterly, mandatory disclosure) |
| Insider trading | SEC Form 4 via EDGAR → FMP → Finnhub | NSE/BSE insider disclosures (SAST/PIT) |
| Analyst estimates | FMP → Finnhub → Yahoo | Yahoo → FMP |
| Guidance | Extracted from transcripts/press releases via LLM (see 06) | Same |
| Peers | FMP peers → Finnhub → same-industry screen from local DB (GICS/sector match, size-banded) | Local DB industry screen |
| Filings / annual reports | SEC EDGAR full-text index (10-K/10-Q/8-K/DEF 14A) | NSE/BSE announcements + company IR page (configurable URL per company) |
| Transcripts | FMP earnings-call transcripts (free tier, limited) → company IR | Company IR |
| News | NewsAPI → GDELT DOC 2.0 → Yahoo Finance news feed | Same + GDELT India filter |
| Risk-free rate / yields | FRED (DGS10, DGS2, DGS3MO) | FRED (IRLTLT01INM156N) → Trading Economics free endpoints → World Bank |
| Inflation / GDP | FRED → World Bank | World Bank → FRED → Trading Economics |
| FX | FRED → Yahoo (`USDINR=X`) → Stooq | Same |
| Commodities | FRED (WTI, gold) → Yahoo futures → Stooq | Same |

Notes and honest constraints:

- **Reuters:** there is no free public Reuters REST API; "Reuters" content arrives
  via NewsAPI/GDELT source filters. (The key you hold is OpenRouter — an LLM gateway
  — and is used by the AI pipeline, not the news fetcher.)
- **NSE/BSE:** official-ish JSON endpoints are unauthenticated but cookie-gated and
  change without notice. The adapters treat them as *fragile tier* — always behind
  Yahoo in the chain, with aggressive circuit breaking. Bhavcopy (EOD CSV) is the
  stable NSE surface and is preferred for historical OHLCV.
- **Alpha Vantage free = 25 req/day.** The budget manager reserves it for gaps the
  free-unlimited tier (Yahoo/Stooq/EDGAR) cannot fill.
- **Macrotrends/IR pages** are HTML scrapes: isolated parsers, tolerant of failure,
  never first in a chain, respect robots.txt.

## 3. Fallback execution semantics

```
async def fetch(capability, company, **params) -> Normalized:
    for adapter in registry.chain(capability, company.region):
        if not budget.allow(adapter):    continue   # quota exhausted → skip
        if breaker.is_open(adapter):     continue   # circuit open → skip
        try:
            result = await adapter.fetch(...)       # retries inside
            validate(result)                        # sanity gates (below)
            return result.with_provenance(adapter)
        except ProviderError as e:
            breaker.record_failure(adapter); log(...)
    raise DataUnavailable(capability, providers_tried=[...])
```

**Validation gates before accepting a provider's answer** (prevents one bad source
poisoning the model): non-empty; dates monotonic; balance sheet balances within 2%;
revenue/assets non-negative; period alignment sane (fiscal year detection); currency
and scale detected (a statement in ₹ crore is normalized to base currency units —
`domain/calc/units.py`). A result failing gates is treated as a provider failure and
the chain continues.

**Cross-source reconciliation:** when two sources are available for statements, the
ingestion service stores the primary (per chain order) and records deltas >5% on key
lines in `data_quality_flags` — surfaced in the API `meta.warnings` and consumed by
the Accounting Red Flag agent.

## 4. Entity resolution ("type any company")

Input: free text (`"apple"`, `"HDFC Bank"`, `"reliance"`, `"NVDA"`, `"TCS.NS"`).

Pipeline (`services/resolution.py`):

1. **Local first:** trigram search (pg_trgm) over `companies.name`,
   `company_aliases.alias`, `listings.ticker`. Confidence from similarity × liquidity
   rank. Hit above threshold → return immediately (cached 7d).
2. **Provider search fan-out:** Yahoo search + FMP search + Alpha Vantage
   SYMBOL_SEARCH in parallel; merge candidates.
3. **Dedupe & canonicalize:** group candidates by (normalized name, country,
   ISIN/CIK when present). One **company** may have many **listings** (Reliance →
   RELIANCE.NS + RELIANCE.BO; Infosys → INFY.NS + INFY ADR). Primary listing =
   home-exchange, highest volume.
4. **Enrich:** US → map to CIK via SEC `company_tickers.json` (enables EDGAR).
   India → match against NSE/BSE master lists (enables shareholding/insider data).
5. **Ambiguity:** if top-2 confidence gap < 0.15, return candidate list and let the
   frontend disambiguate (`POST /companies/resolve` returns `candidates[]`, never
   guesses silently).

Seed job: nightly sync of SEC `company_tickers.json` + NSE/BSE equity master lists
into `companies`/`listings`, so resolution is mostly a local hit.

## 5. Ingestion orchestration

`POST /companies/{id}/refresh` (or first resolve of a new company) enqueues a
**refresh plan** — a Celery chord of per-data-class tasks:

```
resolve_ok ──► [prices, statements_A, statements_Q, actions, ownership,
                estimates, peers, filings_index, news_backfill, macro_context]
                                   │ (parallel, own queues/rate budgets)
                                   ▼
               finalize: recompute derived (ratios, scores) → invalidate caches
                         → emit "company_ready" event → optional AI auto-run
```

Scheduled maintenance (Celery beat):
- EOD price sync for tracked companies (per-exchange close times).
- New-filing watcher (EDGAR RSS / NSE announcements) → invalidate statements,
  re-queue fundamentals + trigger relevant AI agents.
- News poller every 15 min for tracked companies.
- Macro series daily refresh; provider health probe hourly.

## 6. Provenance & confidence

Every stored datum carries `source`, `source_url`, `fetched_at`, and ingestion
`batch_id`. Confidence score per data class =
`f(source_tier, cross_source_agreement, freshness, completeness)` — e.g. EDGAR XBRL
statements score 0.98; a Macrotrends scrape that disagrees with FMP by 8% on EBIT
scores 0.6 and raises a data-quality flag. Valuation traces (05) cite these
per-input confidences and roll them up into the model-level confidence.
