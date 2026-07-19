# 04 — REST API Design (`/api/v1`)

- OpenAPI 3.1 auto-generated; Swagger UI at `/docs`, ReDoc at `/redoc`.
- Auth: `X-API-Key` header (frontend service key). 401/403 problem+json.
- Every response envelope: `{"data": ..., "meta": {"freshness": {...}, "sources": [...],
  "warnings": [...], "request_id": "..."}}`.
- Long-running work returns `202 {task_id}`; poll `GET /tasks/{task_id}`.
- Errors: RFC 7807 `application/problem+json` with typed `code`.

## 1. Company identity & data

```
POST /companies/resolve            {query: "HDFC Bank"} → {match | candidates[]}
GET  /companies/{id}                                    → profile (sector, listings,
                                                          fy-end, description, ir_url)
POST /companies/{id}/refresh       {scope?: [prices, fundamentals, news, ...]}
                                                        → 202 {task_id, batch_id}
GET  /companies/{id}/freshness                          → per-data-class age & source

GET  /companies/{id}/prices        ?range=5y&interval=1d&adjusted=true
GET  /companies/{id}/quote
GET  /companies/{id}/financials    ?statement=income|balance|cashflow|all
                                   &period=annual|quarterly|ttm&limit=10
                                   → canonical line items + as-reported labels,
                                     currency, provenance per statement
GET  /companies/{id}/dividends     | /splits | /buybacks
GET  /companies/{id}/ownership     ?type=institutional|insider|pattern
GET  /companies/{id}/estimates     ?metric=eps|revenue|ebitda
GET  /companies/{id}/guidance
GET  /companies/{id}/peers         ?limit=10          → peer list + method
GET  /companies/{id}/filings       ?type=10-K&limit=20
GET  /companies/{id}/segments                          → revenue/EBIT by segment & geo
```

## 2. Ratios & scores

```
GET /companies/{id}/ratios         ?period=ttm|annual&years=10
    → profitability / liquidity / leverage / efficiency / per-share groups;
      each ratio = {value, formula, inputs:{name,value,source}, series[]}
GET /companies/{id}/ratios/dupont  ?levels=3|5        → full decomposition trace
GET /companies/{id}/scores                            → all score snapshots
GET /companies/{id}/scores/{type}                     → altman_z | piotroski_f |
      beneish_m | quality | growth | momentum | value | profitability | risk |
      composite — with components[] and trace
```

## 3. Assumptions & valuation

```
GET  /companies/{id}/assumptions                       → default set + derivation
                                                         (how each default was built)
POST /companies/{id}/assumptions   {name, based_on?, overrides{...}} → new set
GET  /companies/{id}/assumptions/{set_id}
PUT  /companies/{id}/assumptions/{set_id}              → edit (creates new version)

POST /companies/{id}/valuations/{model}
     model ∈ dcf-fcff | dcf-fcfe | ddm | residual-income | eva | comps |
             precedent-transactions | asset-based | sotp | reverse-dcf |
             expected-return | multiples
     body: {assumption_set_id?, overrides?, peer_ids?}   → 200 ValuationResult
POST /companies/{id}/valuations/monte-carlo-dcf
     body: {assumption_set_id?, distributions{...}, iterations: 10000} → 202 task
POST /companies/{id}/valuations/sensitivity
     body: {model, x_var, y_var, x_range, y_range, steps}  → matrix of fair values
POST /companies/{id}/valuations/scenarios
     body: {scenarios: [{name, assumption_set_id, probability}]}
     → per-scenario values + probability-weighted value + margin of safety
GET  /companies/{id}/valuations/summary
     → football field: every model's {value, low, high, confidence, weight},
       blended intrinsic range, margin of safety vs. price
GET  /valuations/runs/{run_id}                          → stored run incl. FULL trace
GET  /valuations/runs/{run_id}/trace                    → CalcNode tree only
```

`ValuationResult` (shape):

```jsonc
{
  "model": "dcf_fcff",
  "status": "ok",                       // or "not_applicable" + reason
  "fair_value_per_share": 172.34,
  "currency": "USD",
  "price_at_run": 145.20,
  "upside_pct": 18.7,
  "range": {"low": 151.10, "high": 198.60},
  "confidence": 0.78,
  "assumption_set_id": "…",
  "snapshot_id": "…",                   // frozen inputs → reproducible
  "outputs": { "ev": …, "equity_value": …, "pv_explicit": …, "pv_terminal": …,
               "terminal_share_of_ev": 0.62, "wacc": 0.089, "fcff_forecast": [...] },
  "trace": { /* CalcNode tree — see 05 */ }
}
```

## 4. Quant

```
GET /companies/{id}/quant/performance ?window=3y&benchmark=SPX
    → sharpe, sortino, treynor, jensen_alpha, information_ratio, tracking_error,
      max_drawdown — each with formula + inputs
GET /companies/{id}/quant/factors     ?model=capm|ff3|ff5&window=5y
    → betas/loadings, alpha, r², rolling series
GET /companies/{id}/quant/risk        ?window=3y&confidence=0.95,0.99
    → VaR (historical/parametric/MC), CVaR/expected shortfall, vol
GET /companies/{id}/quant/beta        ?window=2y&rolling=90d → rolling beta series
GET /quant/correlations               ?ids=…&window=1y&rolling=90d
    → matrix + rolling pairwise series
POST /companies/{id}/quant/monte-carlo {horizon_days, iterations, method} → 202
```

## 5. News

```
GET  /companies/{id}/news        ?from&to&sentiment&category&min_importance&limit
GET  /news/{article_id}                                → article + analysis
GET  /companies/{id}/news/sentiment-timeline ?window=6m&bucket=1d
POST /companies/{id}/news/refresh                      → 202
GET  /macro/news                 ?country=IN&limit=50
```

## 6. AI analysis

```
POST /companies/{id}/ai/analyze   {agents: ["all"] | [...], force?: bool} → 202 {task_id}
GET  /companies/{id}/ai/analyses  ?agent=&latest=true  → stored structured outputs
GET  /companies/{id}/ai/thesis                         → investment thesis (bull/bear/
                                                         catalysts/risks) latest
GET  /companies/{id}/ai/{agent}   agent ∈ news|financial-statement|macro|industry|
      management|competitive|valuation|risk|moat|red-flags|fraud|esg|swot|
      porter-five-forces
```

## 7. Macro & market context

```
GET /macro/series/{code}          ?from&to            → observations + meta
GET /macro/context                ?country=US|IN      → rf rate, 10y, inflation, GDP
                                                        growth, policy rate, FX — the
                                                        exact values the WACC service
                                                        will use, with sources
GET /macro/commodities            ?codes=WTI,GOLD
```

## 8. Visualization data (chart-ready series)

All endpoints return render-ready arrays (labels + series + annotations), no
client-side math needed:

```
GET /charts/{id}/price-history         ?range=5y&overlays=sma50,sma200
GET /charts/{id}/financial-history     ?metrics=revenue,ebitda,fcf&period=annual
GET /charts/{id}/forecast              ?assumption_set_id=   → history + forecast bands
GET /charts/{id}/dcf-waterfall         ?run_id=   → PV blocks → EV → equity → per share
GET /charts/{id}/sensitivity-matrix    ?run_id=   → heatmap cells + current-cell marker
GET /charts/{id}/monte-carlo-distribution ?run_id= → histogram bins, percentiles, P(loss)
GET /charts/{id}/valuation-bridge      → price vs. each model's fair value (football field)
GET /charts/{id}/revenue-breakdown     ?by=segment|geography&years=5
GET /charts/{id}/margins               ?years=10   → gross/EBITDA/EBIT/net series
GET /charts/{id}/cash-flow             ?years=10   → OCF/ICF/FCF stacked
GET /charts/{id}/balance-sheet         ?years=10   → asset/liability/equity composition
GET /charts/{id}/risk-heatmap          → risk agent output × likelihood/impact grid
GET /charts/{id}/radar-scores          → quality/growth/value/momentum/profitability/risk
GET /charts/{id}/ratio-history         ?keys=roe,roic,de&years=10
GET /charts/{id}/ownership-trend       → institutional/promoter/FII/DII over time
```

## 9. Ops

```
GET /health                      → liveness
GET /health/ready                → DB/Redis/worker checks
GET /health/providers            → per-provider status, quota used, breaker state
GET /tasks/{task_id}             → {status, progress?, result_ref?, error?}
```

## Versioning policy

Path-versioned (`/api/v1`). Additive changes (new fields/endpoints) don't bump the
version; breaking changes ship as `/api/v2` with v1 maintained through a deprecation
window. Response schemas carry `schema_version` in `meta`.
