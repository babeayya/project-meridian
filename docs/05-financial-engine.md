# 05 — Financial Modeling & Valuation Engine

The engine lives in `app/domain/` and is **pure**: inputs in, results + full audit
trace out. No I/O. Services assemble inputs (statements, prices, macro) and persist
results.

## 1. The auditable calculation framework (`domain/calc/trace.py`)

Every calculation returns a `CalcNode`. Composite calculations return trees. This is
the mechanism that makes *every* number reproducible.

```python
class CalcInput(BaseModel):
    name: str                 # "risk_free_rate"
    symbol: str               # "Rf"
    value: Decimal
    unit: str                 # "%", "USD mn", "x"
    source: Provenance        # provider, url, as-of date
    confidence: float         # 0..1

class CalcNode(BaseModel):
    key: str                  # "wacc.cost_of_equity"
    label: str                # "Cost of Equity (CAPM)"
    formula: str              # "Ke = Rf + β × ERP"
    inputs: list[CalcInput]
    substitution: str         # "Ke = 4.28% + 1.24 × 5.00%"
    intermediates: list[CalcNode]   # child calculations
    result: Decimal
    unit: str
    explanation: str          # one-paragraph analyst-grade rationale
    assumptions: list[str]    # explicit assumptions embedded here
    confidence: float         # min/blend of input confidences × method confidence
```

Worked example — the WACC node the API returns (abridged):

```jsonc
{
  "key": "wacc", "label": "Weighted Average Cost of Capital",
  "formula": "WACC = E/(D+E) × Ke + D/(D+E) × Kd × (1 − t)",
  "substitution": "WACC = 0.943 × 9.48% + 0.057 × 4.10% × (1 − 0.162) = 9.13%",
  "result": 0.0913, "unit": "%", "confidence": 0.84,
  "intermediates": [
    { "key": "wacc.cost_of_equity", "formula": "Ke = Rf + β × ERP",
      "inputs": [
        {"name":"risk_free_rate","symbol":"Rf","value":0.0428,
         "source":{"provider":"FRED","series":"DGS10","as_of":"2026-07-08"}},
        {"name":"levered_beta","symbol":"β","value":1.04,
         "source":{"provider":"computed","method":"5y monthly OLS vs SPX",
                   "trace_ref":"quant.beta"}},
        {"name":"equity_risk_premium","symbol":"ERP","value":0.050,
         "source":{"provider":"assumption","basis":"Damodaran implied ERP proxy",
                   "editable":true}}],
      "substitution": "Ke = 4.28% + 1.04 × 5.00% = 9.48%", "result": 0.0948 },
    { "key": "wacc.cost_of_debt",
      "formula": "Kd = Interest Expense / Average Total Debt",
      "substitution": "Kd = 3,933 / ((95,281+96,548)/2) = 4.10%", ... },
    { "key": "wacc.weights", "formula": "E = shares × price; D = total debt", ... },
    { "key": "wacc.tax_rate",
      "formula": "t = Income Tax / Pre-tax Income (3y avg, clamped 0–35%)", ... }
  ]
}
```

Design rules:
- **Units are typed** (`domain/calc/units.py`): a `Money` carries currency + scale;
  mixing INR crore with USD mn raises at construction, not at answer time.
- **`Decimal` end-to-end** for money; floats only inside quant/Monte Carlo.
- Every model version-stamps its trace with `engine_version` (git-derived) so a
  stored run can be re-executed and diffed.

## 2. Canonical statements & derived metrics (`domain/statements/`)

- `taxonomy.py`: ~120 canonical line-item keys with per-provider synonym maps
  ("Net revenue", "Total revenue", "Revenue from operations" → `revenue`).
- `derived.py` computes (each as a `CalcNode`): EBITDA, EBIT, NOPAT,
  gross/operating/net margins, effective tax rate, net debt, invested capital,
  working capital & ΔNWC, FCFF = EBIT(1−t) + D&A − CapEx − ΔNWC,
  FCFE = FCFF − Interest(1−t) + Net Borrowing, TTM aggregation, CAGR helpers.
- **Financial-sector guardrails:** banks/insurers (detected via industry) route to
  equity-side models (DDM, residual income, P/B vs ROE) — FCFF DCF returns
  `not_applicable` with the reason, never nonsense.

## 3. Forecast engine (`domain/forecast/`)

An `AssumptionSet` (editable via API) drives an integrated 3-statement forecast:

| Driver | Default derivation (stored in `derivation` field) | Editable |
|---|---|---|
| Revenue growth (per year, fading) | Blend: 3y/5y historical CAGR, analyst estimates (yrs 1–2), fade to terminal growth by year N | ✓ |
| Gross / EBITDA / EBIT margin path | Historical mean ± trend, capped at best-in-class peer level | ✓ |
| CapEx % of sales; D&A % of gross PP&E | Historical averages, converge to D&A≈CapEx by terminal year | ✓ |
| NWC drivers | DSO/DIO/DPO from history → ΔNWC from revenue/COGS deltas | ✓ |
| Tax rate | 3y effective average, clamped to statutory band | ✓ |
| Debt schedule | Existing maturities + revolver plug; interest = avg balance × Kd | ✓ |
| Share count | Buyback $ ÷ avg price − SBC dilution %; walks share count forward | ✓ |
| Terminal | Gordon growth g (≤ long-run nominal GDP of listing country) AND exit multiple (median peer EV/EBITDA) — both computed, cross-checked, divergence flagged | ✓ |
| Forecast horizon | 5y default, 10y for high-growth (revenue growth > 15%) | ✓ |

The debt schedule closes the loop (interest → net income → retained earnings →
balance sheet balances); a circularity resolver iterates to convergence (≤ 50
iterations, tolerance 1e-6) exactly like an Excel iterative-calc model.

## 4. Valuation models (`domain/valuation/`)

All models return `ValuationResult` with a full trace; all read the same
`AssumptionSet` + statement history + macro context.

| Model | Method summary |
|---|---|
| **DCF (FCFF)** | Forecast FCFF; discount at WACC; terminal = Gordon *and* exit multiple (both reported); EV → −net debt − minorities − prefs + investments → equity → /diluted shares. Terminal-share-of-EV reported as a quality flag. |
| **DCF (FCFE)** | FCFE discounted at Ke; direct equity value. Preferred for banks-adjacent and high-leverage names. |
| **DDM** | Multi-stage (H-model or 2-stage) on DPS; requires dividend history + payout sustainability check; else `not_applicable`. |
| **Residual Income** | BV₀ + Σ PV[(ROEₜ − Ke) × BVₜ₋₁]; clean-surplus BV walk; suits financials. |
| **EVA / Residual Earnings** | NOPAT − WACC × Invested Capital, PV of EVA + IC₀ ⇒ EV; ties to DCF as consistency check (engine asserts DCF≈EVA within tolerance). |
| **Comparable Companies** | Peer set (API-supplied or auto) → EV/EBITDA, EV/Sales, P/E, PEG, P/B, P/CF; quartiles + median applied to target metrics; outlier trimming (IQR); regression option (EV/EBITDA vs growth+margin). |
| **Precedent Transactions** | Deal comps from ingested M&A data (FMP + curated table); control premium noted; wide uncertainty band + lower confidence by construction. |
| **Asset-Based** | Adjusted book value: tangible book, revalue investments/real estate where data allows; floor value for holdcos/deep value. |
| **Sum-of-Parts** | Per reported segment: segment revenue/EBIT × peer multiple of that segment's industry − holdco discount (editable). Requires segment data else `not_applicable`. |
| **Reverse DCF** | Solve (bisection) for the revenue growth / FCF growth implied by the current market price given base margins & WACC; output: "market is pricing X% growth for Y years" + plausibility commentary vs history. |
| **Expected Return** | (Fair value ÷ price)^(1/horizon) − 1 + dividend yield; decomposed into growth + multiple re-rating + yield (Bogle-style). |
| **Monte Carlo DCF** | 10k paths; distributions on growth (normal, μ=base, σ from estimate dispersion), margin (triangular), WACC (normal), terminal g (bounded); outputs: distribution, P5/P25/P50/P75/P95, P(value>price), tornado of variance contributions. Seeded RNG → reproducible. |
| **Sensitivity** | 2-D grid over any two assumption keys (default WACC × terminal g); returns matrix + gradient. |
| **Scenarios** | Named assumption sets (bear/base/bull) with probabilities → probability-weighted value, margin of safety = 1 − price/weighted value. |
| **Summary (football field)** | Aggregates all applicable model runs; weights default by model confidence × sector-fit (e.g. DDM upweighted for utilities); blended intrinsic value **range**, never a false-precision point. |

## 5. Ratio engine (`domain/ratios/`)

~60 ratios in groups (profitability, liquidity, leverage/coverage, efficiency,
per-share, market), each a `CalcNode` with a 10-year series:
ROE, ROA, ROIC, ROCE, margins, current/quick/cash ratios, D/E, net-debt/EBITDA,
interest coverage, asset/inventory/receivables turnover, CCC (DSO+DIO−DPO), FCF
conversion, dividend payout/coverage, EPS/BVPS/FCFPS, and market multiples.
**DuPont:** 3-level (margin × turnover × leverage) and 5-level (tax burden ×
interest burden × EBIT margin × turnover × leverage) with full decomposition trace.

## 6. Score engine (`domain/scores/`)

- **Altman Z** — correct variant per company type (Z for manufacturers, Z' private,
  Z'' non-manufacturer/EM — auto-selected, selection reasoning in trace) + zone.
- **Piotroski F (0–9)** — 9 binary tests, each with the underlying numbers.
- **Beneish M** — 8 indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA), −4.84 +
  weighted sum, manipulation-probability flag; feeds the Fraud/Red-Flag agents.
- **Composite factor scores (0–100, sector-relative percentiles):**
  Quality (ROIC level+stability, margin stability, accruals, leverage),
  Growth (rev/EPS/FCF CAGRs + estimate revisions), Value (earnings/FCF yield, EV
  multiples vs sector), Momentum (6/12m price momentum ex-1m, 52w-high proximity),
  Profitability (margins vs sector), Risk (vol, beta, drawdown, Altman, leverage —
  inverted). **Composite** = weighted blend (weights configurable), with each pillar's
  contribution in the trace.

## 7. Quant engine (`domain/quant/`)

Log returns; benchmark auto-selected by listing (SPX for US, NIFTY 50 for NSE) and
overridable. All metrics report window, frequency, and formula:

- **CAPM / factor models:** OLS beta + Jensen alpha (HAC errors); Fama-French 3/5
  via Ken French library data (US) with graceful degradation to CAPM elsewhere;
  rolling beta (90d/1y windows).
- **Performance:** Sharpe, Sortino (downside deviation), Treynor, Information
  Ratio, Tracking Error, max drawdown, Calmar; rolling Sharpe.
- **Risk:** VaR — historical, parametric (Cornish-Fisher option), Monte Carlo;
  CVaR/Expected Shortfall at 95/99; annualized vol (EWMA option).
- **Correlation:** matrix across requested tickers + rolling pairwise correlation
  vs benchmark/peers.
- **Monte Carlo price simulation:** GBM with drift=μ̂ or rf (both offered),
  seeded, percentile fan output.
