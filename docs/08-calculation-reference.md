# 08 — Calculation Reference: Every Number the Engine Produces

A complete inventory of every calculation in the financial engine (`app/domain/`),
organized by category, with the formula, the method type, and the theory behind it.
Every one of these returns a `CalcNode` (formula + substituted inputs + result +
confidence) — nothing here is a bare number without a traceable derivation.

---

## 0. How to read this document

Each entry is tagged with its **method type**, since that's the first thing an
interviewer will ask about any valuation number:

- **[CASH FLOW MODEL]** — intrinsic value from discounting projected cash flows
- **[MULTIPLE / RELATIVE]** — value inferred from what similar assets trade for
- **[ACCOUNTING-DERIVED]** — a metric computed directly from financial statement line items
- **[RATIO]** — a scale-free relationship between two statement/market figures
- **[SCORE / CLASSIFIER]** — a composite diagnostic (distress, manipulation, quality)
- **[STATISTICAL / QUANT]** — computed from a time series of prices/returns, not fundamentals

---

## 1. Foundational accounting-derived metrics

These aren't valuations themselves — they're the rebuilt "true cash flow" inputs
that every valuation model downstream depends on. Accounting net income is not
cash (it's distorted by non-cash charges, financing structure, and timing), so
these normalize a company's statements into decision-useful figures first.

| Metric | Type | Formula | Why it exists |
|---|---|---|---|
| EBITDA | ACCOUNTING-DERIVED | EBIT + D&A | Operating profit stripped of non-cash D&A and financing/tax — comparable across capital structures and depreciation policies |
| Effective Tax Rate | ACCOUNTING-DERIVED | Income Tax ÷ Pre-tax Income, clamped [0%, 40%] | Clamp guards against one-off items (tax credits, settlements) distorting forward assumptions |
| NOPAT | ACCOUNTING-DERIVED | EBIT × (1 − tax rate) | After-tax operating profit available to **all** capital providers, before financing decisions |
| Working Capital | ACCOUNTING-DERIVED | Current Assets − Current Liabilities | Capital tied up in day-to-day operations |
| Net Debt | ACCOUNTING-DERIVED | Total Debt − Cash − ST Investments | Debt burden net of the liquidity cushion; used in every EV→equity bridge |
| Invested Capital | ACCOUNTING-DERIVED | Total Equity + Total Debt − Cash | Capital actually financing the operating business, used as the ROIC/EVA denominator |
| **FCFF** (Free Cash Flow to Firm) | ACCOUNTING-DERIVED / CASH FLOW INPUT | NOPAT + D&A − CapEx − ΔWorking Capital | Cash available to **all** capital providers (debt + equity) — the input to enterprise-value DCF |
| **FCFE** (Free Cash Flow to Equity) | ACCOUNTING-DERIVED / CASH FLOW INPUT | FCFF − Interest×(1−t) [+ Net Borrowing, assumed 0] | Cash left for equity holders specifically — the input to equity-value DCF |
| Simple FCF | ACCOUNTING-DERIVED | Operating Cash Flow − CapEx | The quick-and-dirty analyst convention, used for FCF yield/margin ratios |

---

## 2. Cost of capital

| Metric | Type | Formula | Notes |
|---|---|---|---|
| Cost of Equity (Ke) | CASH FLOW MODEL INPUT | CAPM: Ke = Rf + β × ERP | Rf = govt bond yield; β = regression-based systematic risk; ERP = equity risk premium (higher for emerging markets, e.g. +150bp for India) |
| Cost of Debt (Kd) | CASH FLOW MODEL INPUT | Interest Expense ÷ Average Total Debt (or Rf + 150bp if unavailable) | Used pre-tax; tax-shielded in WACC |
| **WACC** | CASH FLOW MODEL INPUT | wE×Ke + wD×Kd×(1 − t), market-value weights | The discount rate for enterprise (FCFF) models. Falls back to equity-only weighting (WACC = Ke) if market cap is unavailable |

WACC and Ke are not valuations on their own, but every cash-flow model below is
downstream of them — get these wrong and every DCF-family number is wrong.

---

## 3. Valuation models — the full list, by method type

### 3a. Cash flow models (discount projected cash flows)

| Model | Type | Discounts | Rate | Core formula |
|---|---|---|---|---|
| **DCF (FCFF)** — primary/default model | CASH FLOW MODEL | Unlevered FCF | WACC | EV = ΣPV(FCFF) + PV(Terminal Value); Terminal Value (Gordon) = FCFF_final×(1+g)/(WACC−g), cross-checked against an exit-multiple terminal value. Equity Value = EV − Net Debt − Minorities; ÷ diluted shares |
| **DCF (FCFE)** — secondary/equity-side model | CASH FLOW MODEL | Levered FCF | Ke (cost of equity) | Equity Value = ΣPV(FCFE) + PV(Terminal Value), discounted directly at Ke — no EV/equity bridge needed since it already lands on equity value |
| **DDM** (Dividend Discount Model) | CASH FLOW MODEL | Dividends per share | Ke | Two-stage: near-term growth from historical DPS CAGR (clamped [-5%,15%]), fading linearly to a terminal growth rate, then Gordon-growth terminal value. Requires ≥3 years of dividend history |
| **Residual Income** | CASH FLOW MODEL (equity-side) | "Excess" earnings, not raw cash flow | Ke | V = Book Value₀ + Σ PV[(ROE_t − Ke) × Book Value_{t-1}], ROE fades to Ke over 10y (competitive convergence), clean-surplus book value walk-forward |
| **EVA** (Economic Value Added) | CASH FLOW MODEL (enterprise-side) | "Excess" economic profit | WACC | V = Invested Capital₀ + Σ PV[(ROIC_t − WACC) × Invested Capital_{t-1}], ROIC fades to WACC over 10y. Mathematically should converge with FCFF DCF — used internally as a consistency cross-check |
| **Reverse DCF** | CASH FLOW MODEL (solved backwards) | FCFF | WACC | Same FCFF engine, but solves (via bisection) for the constant growth rate that makes DCF value = current market price. Answers "what growth is the market pricing in?" |
| **Scenario (bear/base/bull)** | CASH FLOW MODEL (probability-weighted) | FCFF | WACC | Re-runs the full FCFF DCF under 3 named cases (default 25/50/25% probability) with perturbed growth/margin/terminal-growth; output = probability-weighted fair value + margin of safety |
| **Monte Carlo DCF** | CASH FLOW MODEL (simulated) | FCFF | WACC | 10,000 seeded draws with growth ~ Normal, margin ~ Triangular, WACC ~ Normal, terminal g ~ Uniform; outputs a full fair-value distribution (P5–P95) and P(fair value > price) |
| **Expected Return** | derived from a cash flow model's output | — | — | (Fair Value ÷ Price)^(1/years) − 1 + Dividend Yield — annualized return to a DCF-derived fair value, decomposed into price appreciation + yield |

### 3b. Multiple / relative valuation models

| Model | Type | Multiples used | Method |
|---|---|---|---|
| **Historical Multiples** | MULTIPLE / RELATIVE | P/E, P/B, P/S (company's own history) | Median of the company's own historical multiples applied to current EPS/BVPS/Sales-per-share. A mean-reversion bet — silent on whether the history itself was ever fairly priced |
| **Peer Comparable Companies (Comps)** | MULTIPLE / RELATIVE | P/E, P/B, P/S, EV/EBITDA (peer set) | Median of ≥3 peers' multiples (IQR-trimmed to remove outliers) applied to the target's fundamentals. The most commonly used method on the sell side — fewest assumptions, most dependent on picking a genuinely comparable peer set |

### 3c. Asset-based / floor valuation

| Model | Type | Formula |
|---|---|---|
| **Asset-Based (Tangible Book Value)** | ACCOUNTING-DERIVED / FLOOR VALUE | (Total Equity − Goodwill − Intangibles) ÷ Diluted Shares — a liquidation-style floor, ignoring going-concern value. Most meaningful for asset-heavy or deep-value names |

### 3d. Aggregation

| Output | Type | Method |
|---|---|---|
| **Sensitivity Grid** | diagnostic, not a valuation | 2D grid of DCF fair values across a WACC × terminal-growth matrix — shows how fragile the point estimate is |
| **Summary / Football Field** | blended aggregate | Confidence × model-reliability-weighted blend of every applicable model above (FCFF weighted highest at 30%, asset-based lowest at 5%), reported as a **range**, never a single point |

---

## 4. Ratio analysis — [RATIO] category, ~40 ratios in 5 groups

All are scale-free relationships between two line items; each is independently
omitted (not zeroed/faked) if an input is missing.

**Profitability**
- Gross Margin = Gross Profit / Revenue
- Operating Margin = EBIT / Revenue
- Net Margin = Net Income / Revenue
- EBITDA Margin = EBITDA / Revenue
- ROE (Return on Equity) = Net Income / Total Equity
- ROA (Return on Assets) = Net Income / Total Assets
- **ROIC** (Return on Invested Capital) = NOPAT / Invested Capital — "the moat metric": compare to WACC to judge value creation
- FCF Margin = Free Cash Flow / Revenue

**Liquidity**
- Current Ratio = Current Assets / Current Liabilities
- Quick Ratio = (Current Assets − Inventory) / Current Liabilities
- Cash Ratio = Cash / Current Liabilities

**Leverage / Coverage**
- Debt / Equity = Total Debt / Total Equity
- Net Debt / EBITDA
- Interest Coverage = EBIT / Interest Expense
- Liabilities / Assets

**Efficiency**
- Asset Turnover = Revenue / Total Assets
- DSO (Days Sales Outstanding) = Receivables × 365 / Revenue
- DIO (Days Inventory Outstanding) = Inventory × 365 / COGS
- DPO (Days Payables Outstanding) = Payables × 365 / COGS
- **Cash Conversion Cycle** = DSO + DIO − DPO

**Market (needs live price)** — [RATIO], market-based
- P/E = Price / EPS
- P/B = Price / Book Value per Share
- P/S = Market Cap / Revenue
- EV/EBITDA = (Market Cap + Net Debt) / EBITDA
- EV/Sales = EV / Revenue
- FCF Yield = FCF / Market Cap
- Dividend Yield = Dividends Paid / Market Cap

**DuPont Decomposition** [RATIO, decomposition]
- 3-level: ROE = Net Margin × Asset Turnover × Financial Leverage
- 5-level: ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Leverage
  (falls back to 3-level if pretax income data is unavailable)
  — isolates *why* ROE is what it is: genuine operating performance vs. financing
  structure vs. tax efficiency.

---

## 5. Diagnostic scores — [SCORE / CLASSIFIER]

| Score | Type | What it predicts | Method |
|---|---|---|---|
| **Altman Z-Score** | SCORE / CLASSIFIER | Bankruptcy/distress risk | Weighted sum of 5 ratios (working capital/assets, retained earnings/assets, EBIT/assets, market equity/liabilities, sales/assets). Auto-selects variant: original Z for public manufacturers (needs market cap), Z'' for non-manufacturers/emerging markets (uses book equity instead). Not defined for banks/insurers — leverage is their business model, not a distress signal |
| **Piotroski F-Score** | SCORE / CLASSIFIER | Fundamental quality (0–9) | 9 binary year-over-year tests: profitability (ROA positive, ROA improving, OCF positive, accruals quality), leverage/liquidity (leverage falling, current ratio improving, no dilution), efficiency (margin improving, turnover improving) |
| **Beneish M-Score** | SCORE / CLASSIFIER | Earnings manipulation probability | 8 indices (days-sales-in-receivables, gross margin, asset quality, sales growth, depreciation, SG&A, total accruals, leverage) combined via fixed 1999 regression coefficients into M = −4.84 + Σ(coefficient × index). M > −1.78 flags elevated manipulation risk |

---

## 6. Composite factor scores — [SCORE], 0–100 scale, sector/absolute rubrics

| Pillar | What it measures | Key inputs |
|---|---|---|
| Quality | Durability & cleanliness of earnings | ROIC level, margin volatility (5y), accruals (NI vs OCF gap), leverage |
| Growth | Trajectory | Revenue CAGR (3y/5y), Net Income CAGR, OCF CAGR |
| Profitability | Absolute margin/return levels | Gross/operating/net margin, ROE |
| Value | Cheapness | Earnings yield, FCF yield, Price/Book |
| Momentum | Recent price trend | 6-month return, 12-month return, % off 52-week high |
| Risk (inverted — higher = safer) | Downside exposure | 1y annualized volatility, 1y max drawdown, Altman Z zone |
| **Composite** | Blended overall score | Weighted average of the 6 pillars (default: Quality 25%, Growth 20%, Value 20%, Profitability 15%, Momentum 10%, Risk 10%) |

---

## 7. Quantitative / statistical metrics — [STATISTICAL / QUANT]

Computed from time series of daily prices/returns, not from financial statements.

**Market model**
- **Beta (β)** = Cov(stock returns, benchmark returns) / Var(benchmark returns) — OLS regression, feeds directly into CAPM/Ke above
- **Jensen's Alpha** = actual return − CAPM-predicted return — genuine outperformance beyond what beta exposure would predict
- **R²** — how much of the stock's return variance the benchmark explains

**Performance (risk-adjusted return)**
- **Sharpe Ratio** = (Return − Rf) / Total Volatility
- **Sortino Ratio** = (Return − Rf) / Downside Volatility only (ignores upside swings)
- **Treynor Ratio** = (Return − Rf) / Beta (systematic risk only, for diversified holders)
- **Information Ratio** = Active Return vs. benchmark / Tracking Error
- **Tracking Error** = volatility of (stock return − benchmark return)
- **Calmar Ratio** = Annualized Return / |Max Drawdown|

**Risk**
- **Max Drawdown** = largest peak-to-trough decline in the price series
- **VaR (Value at Risk)**, historical and parametric (95%/99%) — worst expected loss at a confidence level
- **CVaR / Expected Shortfall** — average loss *beyond* the VaR threshold (captures tail severity VaR itself ignores)
- **Annualized Volatility** — standard deviation of daily returns, annualized

**Rolling / momentum**
- Rolling Beta and Rolling Sharpe (90-day window default) — how these metrics evolve through time rather than a single static number
- Momentum stats: 6-month return, 12-month return, % off 52-week high (feeds the Momentum factor pillar above)

---

## 8. Quick-reference: "is this a multiple or a cash flow model?"

**Cash flow models** (discount projected/derived cash flows or economic profit):
DCF (FCFF), DCF (FCFE), DDM, Residual Income, EVA, Reverse DCF, Scenario, Monte Carlo DCF

**Multiples / relative valuation** (value inferred from comparable trading multiples):
Historical Multiples, Peer Comps (P/E, P/B, P/S, EV/EBITDA)

**Neither — a floor / diagnostic, not an intrinsic estimate:**
Asset-Based (Tangible Book Value), Sensitivity Grid, Expected Return (derived from a DCF output, not a standalone model)

**Aggregator:** Summary / Football Field — blends all of the above into one range

---

## 9. The one-paragraph version, if asked to summarize in an interview

The engine rebuilds true cash flow from raw financial statements (EBITDA → NOPAT →
FCFF/FCFE), prices the risk of that cash flow via CAPM/WACC, then values the company
three fundamentally different ways — discounting projected cash flows (DCF/DDM/RI/EVA
family), inferring value from what comparable assets trade for (multiples/comps), and
a liquidation floor (tangible book) — cross-checks the cash-flow-based answer with
probabilistic methods (scenarios, Monte Carlo) instead of pretending to false
precision, and separately runs ratio analysis, distress/manipulation screens (Altman
Z, Piotroski F, Beneish M), factor scoring (quality/growth/value/momentum/risk), and
market-based quant statistics (beta, Sharpe, VaR) as independent diagnostic lenses on
top of the valuation itself.
