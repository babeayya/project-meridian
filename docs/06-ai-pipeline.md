# 06 — AI Analysis Engine & News Pipeline

## 1. LLM access

- **Gateway:** OpenRouter (`providers/llm/openrouter.py`) — one client, many models.
  Key from `OPENROUTER_API_KEY` env var only.
- **Model routing (config, not code):** default `anthropic/claude-sonnet-4.5` for
  analysis agents; a cheap fast model (e.g. `anthropic/claude-haiku-4.5`) for bulk
  news classification; long-context model for full 10-K passes. Per-agent override
  in config.
- **Structured output contract:** every agent has a Pydantic schema. The client
  requests JSON (response_format where supported, else schema-in-prompt), validates
  with Pydantic, and on failure runs **schema repair**: re-ask once with the
  validation errors; second failure → task error (never store junk).
- **Cost & audit:** tokens in/out, cost, model, `prompt_version` stored on every
  `ai_analyses` row. Prompts are versioned files in-repo
  (`services/ai/agents/prompts/<agent>/v003.md`).

## 2. Agent design

Each agent = **context builder** (deterministic SQL pulls, token-budgeted) +
**versioned prompt** + **output schema** + **confidence rubric**. Agents never fetch
the web themselves; they only see data already ingested (reproducibility + injection
containment — external text is fenced and marked untrusted).

| Agent | Context pack | Output schema (JSON, abridged) |
|---|---|---|
| **News** | Last 90d classified articles, sentiment timeline | `{narrative, key_events[], sentiment_trend, expected_impacts[{event, segment, direction, magnitude, horizon}], confidence}` |
| **Financial Statement** | 5y canonical statements, ratio series, data-quality flags | `{revenue_quality, margin_analysis, cash_conversion, balance_sheet_strength, working_capital_trends, notable_items[], trend_flags[], confidence}` |
| **Macro** | `/macro/context` for listing country + sector sensitivities | `{rate_sensitivity, fx_exposure, inflation_passthrough, cycle_position, macro_risks[], tailwinds[], confidence}` |
| **Industry** | Sector data, peer metrics, industry multiples | `{industry_structure, growth_outlook, key_drivers[], disruption_risks[], target_position, confidence}` |
| **Management** | Guidance history vs actuals, insider trades, transcript excerpts, compensation (DEF 14A) | `{guidance_accuracy_score, capital_allocation_grade, alignment_signals[], red_flags[], track_record[], confidence}` |
| **Competitive** | Peer comparison table (share, margins, ROIC, growth) | `{market_position, share_trend, relative_strengths[], weaknesses[], competitive_threats[], confidence}` |
| **Moat** | ROIC vs WACC 10y series, margins vs peers, industry agent output | `{moat_rating: none|narrow|wide, sources[{type: brand|network|switching_costs|cost_advantage|intangibles|scale, evidence, durability}], trend, confidence}` |
| **Valuation** | All model runs + traces, football field, reverse-DCF output | `{fair_value_assessment, model_agreement, key_assumption_risks[], implied_expectations_view, recommended_range, confidence}` |
| **Risk** | All above + quant risk metrics + red flags | `{risks[{name, category, likelihood: 1-5, impact: 1-5, mitigants, monitoring_kpis[]}], top_3, heatmap_data, confidence}` (feeds `/charts/risk-heatmap`) |
| **Accounting Red Flag** | Beneish components, accruals ratio, revenue vs receivables/CFO divergence, auditor changes, restatements, cross-source deltas | `{flags[{code, severity, evidence_numbers, explanation}], overall_grade, confidence}` |
| **Fraud Detection** | Red-flag output + related-party items + promoter pledging (IN) + short-interest context | `{fraud_risk_score, patterns_matched[], evidence[], recommended_diligence[], confidence}` — framed as diligence signals, not accusations |
| **ESG** | News (ESG-tagged), filings mentions, controversy screen | `{e_score, s_score, g_score, controversies[], governance_notes[], data_coverage_caveat, confidence}` |
| **Thesis (synthesizer)** | Outputs of ALL agents + valuation summary | `{investment_thesis, bull_case[], bear_case[], catalysts[{event, window, direction}], risks[], swot{s[],w[],o[],t[]}, porter_five_forces{...}, business_quality_score, valuation_summary, management_quality, growth_drivers[], recommendation_stance, confidence}` |

**Orchestration** (`services/ai/orchestrator.py`): DAG — independent agents fan out
in parallel Celery tasks; `Moat` waits on `Industry`; `Risk` and `Fraud` wait on
`Red Flag`; `Thesis` is the terminal reduce node. Partial failure tolerated: thesis
runs with available agents and lists gaps in `data_coverage_caveat`.

**Guardrails:** every agent's system prompt requires it to (a) cite which input
numbers drove each claim (by reference key), (b) emit `confidence` per rubric,
(c) say "insufficient data" instead of inventing, (d) treat quoted news/filing text
as data, not instructions. Numeric claims in outputs are spot-validated against the
context pack; mismatches lower stored confidence and are flagged.

## 3. News engine (`services/news.py`)

**Sources:** NewsAPI (key required) → GDELT DOC 2.0 (free, historical reach) →
Yahoo Finance news. Reuters/major-wire content is captured through these
aggregators' source filters (no free direct Reuters API exists).

Pipeline per company (poll 15 min for tracked companies + on-demand refresh):

1. **Fetch** from all available sources in parallel (company name + ticker + alias
   queries, language filter).
2. **Dedupe:** URL canonicalization hash, then near-dup title similarity
   (rapidfuzz ≥ 0.9) across outlets — keep highest-authority outlet.
3. **Classify (LLM, cheap model, batched 10–20 articles/call):** sentiment
   (positive/neutral/negative + score −1..1), confidence, importance 0..1 (outlet
   authority × event materiality × company specificity), category (earnings, M&A,
   regulatory, product, management, macro), affected segments, expected financial
   impact (direction + qualitative magnitude + rationale).
4. **Persist** article + analysis; sentiment timeline is a SQL aggregate (no
   recompute).
5. Breaking-news heuristic: published <2h, importance >0.8 → flagged `breaking`,
   optional webhook for the frontend.

Press releases & transcripts enter via the filings ingestion path (8-K, IR pages,
FMP transcripts) and feed the Management/Guidance extraction job: an LLM pass over
each new transcript extracts `management_guidance` rows (metric, range, verbatim
quote, confidence) — the guidance table in 03.

## 4. What the LLM is NOT allowed to do

- Never computes valuations or ratios — it interprets engine outputs. All arithmetic
  lives in `domain/` (deterministic, traced).
- Never sees raw provider credentials or URLs to fetch.
- Never writes to any table except through validated schemas into `ai_analyses` /
  `news_analysis` / `management_guidance`.
