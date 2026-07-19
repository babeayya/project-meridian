# 08 — Valuation Theory & Interview Defense Guide (Project Meridian)

> **Purpose of this document.** This is not a code reference. It is a first-principles
> finance curriculum built around the *exact* calculations, formulas, and hardcoded
> numbers your engine uses (`app/domain/`, `app/services/`). Read it as if you must
> defend every assumption in this project before a CFA charterholder, an IB MD, a PE
> principal, and a corporate-finance professor — all in the same room.
>
> **How it's organized.** Part A teaches each component the way an interviewer will
> attack it (Purpose → Theory → Why this number → Formula → Why not the alternative →
> Interview defense → Edge cases). Part B is the global layer: how the Street actually
> does this, what your project is missing, a full knowledge graph, learning drills, and
> a defense scorecard with a study roadmap.
>
> **How to study with it.** For each topic: (1) read the theory, (2) attempt the
> learning-mode questions *before* looking anything up, (3) rehearse the interview-defense
> exchange out loud. The trick questions are where interviews are actually won or lost.

---

# PART A — COMPONENT-BY-COMPONENT TEACHING

## Table of contents
- A0. The mental model of all valuation (read this first)
- A1. Financial statements → normalized cash flow (EBITDA, NOPAT, FCFF, FCFE)
- A2. The risk-free rate (DGS10 / India 10Y)
- A3. Beta (2y OLS regression)
- A4. Equity risk premium (5% / 6.5%)
- A5. Cost of equity — CAPM
- A6. Cost of debt & the tax shield
- A7. WACC
- A8. The DCF (FCFF) — your primary model
- A9. Terminal value (Gordon vs exit multiple)
- A10. The EV → Equity bridge
- A11. FCFE DCF, DDM, Residual Income, EVA
- A12. Relative valuation (historical multiples & peer comps)
- A13. Reverse DCF, Scenarios, Monte Carlo, Sensitivity
- A14. Ratios & DuPont
- A15. Diagnostic scores (Altman, Piotroski, Beneish)
- A16. Factor scores
- A17. Quant/statistical layer (beta, Sharpe, VaR, etc.)

---

## A0. The mental model of all valuation

Before any component: there are only **three** ways to value anything, and your project
does all three. An interviewer's first question is often "walk me through your
approaches" — you must be able to name and contrast them instantly.

1. **Intrinsic / DCF** — value = present value of future cash flows. "What is it worth
   based on the cash it generates?" (Your DCF-FCFF, DCF-FCFE, DDM, RI, EVA.)
2. **Relative / multiples** — value = what the market pays for comparable assets. "What
   are similar things trading for?" (Your historical multiples, peer comps.)
3. **Asset-based / contingent claim** — value = net worth of the assets, or option value.
   "What would the pieces fetch?" (Your tangible book value floor.)

The single unifying equation of intrinsic value:

```
Value = Σ [ CashFlow_t / (1 + r)^t ]      for t = 1 … ∞
```

Everything else — WACC, beta, terminal value, the EV bridge — exists only to make
that one equation operational: *what* cash flow (numerator), at *what* discount rate
(denominator), for *how long* (horizon + terminal value).

**Damodaran's framing** (memorize this): every valuation is a set of *stories* about
growth, margins, reinvestment, and risk, converted into numbers. Your job in an
interview is to defend the *story*, not the arithmetic.

---

## A1. From financial statements to normalized cash flow

### PART 1 — Purpose
Accounting earnings are not cash. Net income is distorted by (a) non-cash charges
(depreciation), (b) financing structure (interest), (c) accrual timing (revenue booked
before cash arrives). Before you can discount "cash flow," you must *rebuild* it from
the three statements. This component (`app/domain/statements/derived.py`) is the
foundation every intrinsic model stands on. Remove it and you'd be discounting
accounting fiction.

### PART 2 — Theory
The income statement, balance sheet, and cash-flow statement are three views of the same
business. Valuation cares about **cash available to capital providers**, which the raw
statements never report directly — you assemble it. The historical arc: pre-1980s
analysts valued on earnings/dividends; Rappaport (*Creating Shareholder Value*, 1986)
and later Damodaran formalized *free cash flow* as the correct valuation numerator
because dividends are a policy choice and earnings are an accounting choice, but free
cash flow is what the business actually throws off.

### PART 4 — Every formula (with definitions, intuition, worked example)

**EBITDA = EBIT + D&A**
- *EBIT* (operating income) = profit from operations before interest and tax.
- *D&A* = depreciation & amortization (non-cash allocation of past capex).
- *Why it works*: strips out capital-structure (interest), tax-regime, and
  depreciation-policy differences → a cleaner cross-company operating-profit comparison.
- *Mistake*: treating EBITDA as cash flow. It ignores capex, working capital, and taxes
  — "EBITDA is what you'd earn if you never had to reinvest, pay taxes, or service debt,"
  i.e. a fantasy. Charlie Munger: "think about it every time you hear 'EBITDA', substitute
  'bullshit earnings'." Know both the use and the critique.

**Effective tax rate = Income Tax ÷ Pre-tax Income**, clamped to **[0%, 40%]**.
- *Why clamp*: a one-off tax credit or a settlement can produce a −200% or +90% effective
  rate for one year, which would wreck a forward forecast. The clamp is a *robustness*
  choice, not a theory statement. (Defense: "I clamp to avoid one-off items distorting a
  forward-looking assumption; the statutory US federal rate is 21%, so 40% is a generous
  upper bound that still catches state + international mix.")

**NOPAT = EBIT × (1 − t)** — *Net Operating Profit After Tax.*
- The after-tax profit the operating business would earn **if it had no debt**. Critical:
  we tax EBIT (not net income) because we want operating profit *unlevered* — financing
  is handled separately in the discount rate. This is the number that feeds FCFF.

**FCFF = NOPAT + D&A − CapEx − ΔNWC** *(your code: NOPAT + D&A − CapEx + ΔWC(cash))*
- *FCFF* = Free Cash Flow to the **Firm** = cash to **all** capital providers (debt +
  equity), before financing.
- *+ D&A*: add back the non-cash charge that reduced NOPAT.
- *− CapEx*: subtract real cash spent on long-term assets.
- *− ΔNWC*: subtract cash tied up in growing working capital (receivables + inventory −
  payables). Growth *consumes* cash before it *produces* it.
- **[THIS IS A CASH-FLOW-MODEL INPUT]** — FCFF is what you discount at WACC.
- *Worked example*: EBIT 1,000, t = 25% → NOPAT 750. D&A 200, CapEx 300, ΔNWC 50.
  FCFF = 750 + 200 − 300 − 50 = **600**.

**FCFE = FCFF − Interest×(1 − t) + Net Borrowing** *(your code assumes Net Borrowing = 0)*
- *FCFE* = Free Cash Flow to **Equity** = cash left for shareholders after debt service.
- Subtract after-tax interest (debt holders paid first); add net new borrowing (debt
  raised is cash *to* equity in that period). **[CASH-FLOW-MODEL INPUT — discounted at Ke.]**
- *Worked example*: FCFF 600, interest 80, t = 25% → after-tax interest 60. Net borrowing
  0. FCFE = 600 − 60 = **540**.

### PART 5 — Why not something else?
Why FCF and not **dividends** as the base? Dividends understate value for companies that
retain cash (Google paid none for 20 years — a DDM would have valued it near zero). Why
not **net income**? It's post-interest (capital-structure contaminated) and non-cash.
FCF is the theoretically correct, policy-neutral numerator.

### PART 7 — Edge cases
- **Negative FCF** (high-growth/startup): a single-stage DCF breaks. You must forecast to
  the point FCF turns positive (multi-stage). Your engine flags terminal-year negative
  FCFF and refuses (`ValuationOutcome.na`) rather than printing garbage.
- **Financials** (banks/insurers): FCFF is meaningless — for a bank, debt *is* raw
  material, not financing, and "capex/NWC" don't separate cleanly. Your engine routes
  financials away from FCFF/EVA to DDM/Residual Income. Know *why*: you can't cleanly
  split operating vs financing for a business whose operations *are* financing.

> **Learning mode — A1**
> Conceptual: (1) Why tax EBIT rather than pre-tax income for NOPAT? (2) Why add back
> D&A but subtract CapEx when they're often similar in size? (3) Why does revenue growth
> *consume* cash via ΔNWC? (4) When would FCFF < FCFE? (5) Why is EBITDA not free cash flow?
> Numerical: (1) EBIT 500, t 21%, D&A 120, CapEx 90, ΔNWC −30 → FCFF? (2) FCFF 380,
> interest 40, t 21%, net borrowing 25 → FCFE? (3) If ΔNWC swings from −20 to +60, what
> happens to FCFF? (4) A firm with D&A 200 and CapEx 200 in steady state — what's the net
> reinvestment effect? (5) EBIT 1,000, effective tax computed as 480/1,000 — is the clamp
> triggered?
> Interview: (1) "Your effective rate came out 45% — defend the clamp." (2) "Why not just
> use the statutory rate everywhere?" (3) "A CFO tells you EBITDA is up 20% — why don't you
> care?" (4) "Walk me from net income to FCFF." (5) "Where does stock-based compensation fit,
> and did your model handle it?"
> Trick: (1) "If D&A is non-cash, why does a higher D&A raise FCFF but not change a
> pre-tax-based FCF?" (2) "A company with negative working capital (Amazon) — is growth
> a cash source or sink for it?" (3) "Your FCFE assumes net borrowing = 0. Name the exact
> situation where that assumption most overvalues equity."

---

## A2. The risk-free rate (Rf)

### PART 1 — Purpose
Rf is the return on a "guaranteed" cash flow. It's the anchor of *every* discount rate:
it sits inside Ke (CAPM) and inside Kd (your Rf + 150bp fallback). Get Rf wrong by 1%
and a DCF fair value can move 15–25%. It exists because money has time value even with
zero risk — a rupee today beats a guaranteed rupee next year.

### PART 2 — Theory
"Risk-free" means *no default risk* and *no reinvestment/price risk over the horizon*.
A government bond in its **own currency** is the proxy: a sovereign can always print its
own currency to repay (so nominal default risk ≈ 0). Duration must match the cash flows:
DCFs discount effectively perpetual flows, so you use a **long** bond (10-year), not a
T-bill. The 10-year is the market convention — long enough to match, liquid enough to be
clean.

### PART 3 — Why THIS value?
Your engine (`app/services/macro.py`):
- **US/Global → FRED `DGS10`** (10-Year US Treasury Constant Maturity). **India →
  `INDIRLTLT01STM`** (India 10-Year). *Region-matched by design.*
- **Hardcoded fallbacks if the API is down: US 4.2%, India 7.0%, Global 4.5%.**
- *Why region-matched*: the risk-free rate must be in the **same currency and inflation
  regime as the cash flows**. India's ~7% vs US ~4% is mostly *expected INR inflation*
  (Fisher: nominal ≈ real + expected inflation). Discounting rupee flows at a Treasury
  yield double-counts nothing and mismatches inflation — theoretically wrong.
- *Is it fixed?* No — fetched live, most-recent non-null observation. Defaults only on
  outage, and the source label degrades to `assumption:default` so confidence drops.
- *If Rf ↑*: discount rate ↑ → value ↓ (and vice versa). This is why 2022's rate hikes
  crushed long-duration/growth valuations — their cash flows are far in the future, so
  they're most sensitive to the denominator.

### PART 5 — Why not something else?
- **Why not the 3-month T-bill (DGS3MO)?** Duration mismatch — understates the discount
  rate for long-dated flows → systematic *overvaluation*. Use short rates only for
  short-horizon or trading contexts.
- **Why not the 30-year?** Thinner/more volatile; convention is the 10-year.
- **Why not a "normalized" Rf** (Damodaran sometimes advocates a smoothed long-run rate)?
  Defensible in ZIRP environments where spot rates are artificially low; your engine uses
  spot for objectivity and provenance. Know the trade-off: spot = market-consistent but
  noisy; normalized = stable but subjective.

### PART 6 — Interview defense (rehearse this exchange)
- Q: *"Why a 10-year Treasury and not a 30-year or a T-bill?"* → duration-matching to
  perpetual DCF flows; 10Y is the liquid convention.
- Q: *"US company with global operations — one Rf or many?"* → ideally value each
  geography's cash flows in its own currency at its own Rf, or do everything in one
  currency and adjust for inflation differentials via forward FX. Your engine uses the
  *listing* region — a simplification; be ready to concede it.
- Q (trick): *"Rates went negative in Europe. Is a negative Rf valid in CAPM?"* → Yes
  mechanically, but it breaks intuition; practitioners floor Rf or use a normalized rate.

### PART 7 — Edge cases
Emerging-market sovereign in *local* currency still carries inflation risk (captured);
sovereign in *hard* currency (USD-denominated EM debt) carries **default** risk, so it's
*not* risk-free — you'd strip the country default spread out. Your India series sidesteps
this by using the local-currency long rate.

> **Learning mode — A2**
> Conceptual: (1) Why is a government bond "risk-free" but a AAA corporate isn't? (2) Why
> match duration? (3) What does the India–US yield gap mostly represent? (4) Why does a
> higher Rf hurt growth stocks more than value stocks? (5) When is spot Rf a bad choice?
> Numerical: (1) DCF value with Rf 4% vs 5%, all else equal, cash flow far-dated — direction
> and rough magnitude? (2) Real rate 2%, expected inflation 5% — approximate nominal Rf?
> Interview/trick: (1) "Defend using spot over normalized in a zero-rate world." (2) "Your
> API failed and used the 4.2% default — how does that show up in your output's credibility?"
> (3) "Is the 10Y yield the risk-free rate, or the risk-free rate *plus* a term premium?"

---

## A3. Beta (β)

### PART 1 — Purpose
Beta measures **systematic risk** — how much a stock moves with the market. It's the only
company-specific input in CAPM, translating "market risk premium" into "*this* stock's
required premium." Remove it and CAPM can't distinguish a utility from a semiconductor.

### PART 2 — Theory
From Markowitz portfolio theory → CAPM (Sharpe/Lintner, 1964): diversification eliminates
*idiosyncratic* (company-specific) risk for free, so the market only *pays* you for
**non-diversifiable** (systematic) risk. Beta is that quantity: the covariance of the
stock with the market, scaled by market variance. β = 1 → moves with the market; β > 1 →
amplifies; β < 1 → dampens; β < 0 → moves opposite (rare — gold miners, some hedges).

### PART 3 / 4 — Why THIS value & the formula
Your engine (`app/domain/quant/engine.py`, `capm()`):
```
β = Cov(R_stock, R_market) / Var(R_market)
```
computed by **OLS regression of 2 years of daily log returns** against the region's index
(`^GSPC` US / `^NSEI` India). **Fallback β = 1.0** if < 120 days of history or the
benchmark is unavailable.
- *Why 2y daily*: bias-variance trade-off. 5y monthly (Damodaran's default) is less noisy
  but stale for fast-changing firms; 2y daily is more responsive but noisier and suffers
  microstructure bias. Both are defensible — *know you chose responsiveness over stability*.
- *Why β = 1 fallback*: the least-informative prior — "assume market-average risk when I
  can't measure it." Honest and conservative-ish.
- *If β ↑*: Ke ↑ → WACC ↑ → value ↓.

### PART 5 — Why not something else? (regression β vs alternatives)
- **Bloomberg "adjusted beta"** = 0.67×raw + 0.33×1.0 (Blume adjustment) — betas
  mean-revert to 1 over time; pros almost always use adjusted. *Your engine uses raw β —
  a defensible gap to flag.*
- **Bottom-up / unlevered beta** (Damodaran's preferred): average the unlevered betas of
  the industry, then re-lever at the target's capital structure. More stable, forward-looking,
  works for private firms and IPOs. **Your engine does NOT unlever/relever — this is the
  single most likely beta attack in an interview.** (See PART 6.)
- **Fundamental betas** (Barra) — multifactor risk models; institutional, data-heavy.

### PART 6 — Interview defense
- Q: *"Why not unlever the beta?"* → Unlevering removes the effect of the peer's/own
  leverage so you get *asset* (business) risk, then re-lever at *your* target structure.
  It's superior when (a) capital structure will change, (b) the firm is private/pre-IPO, or
  (c) the regression β is unreliable. Concede your engine uses a direct regression β and
  say *when* you'd switch: `βL = βU × [1 + (1−t)×D/E]` (Hamada). **Be ready to write Hamada.**
- Q (trick): *"What if beta is negative?"* → Ke = Rf + (negative)×ERP < Rf, i.e. the model
  says investors accept *less* than the risk-free rate because the asset is a hedge (pays
  off in bad states). Mechanically valid, rare, and you'd sanity-check the regression window.
- Q: *"Your R² is 0.15 — is that beta usable?"* → Low R² means the market explains little of
  the stock's variance (lots of idiosyncratic risk); the β point estimate has a wide standard
  error. You'd widen to industry/bottom-up beta.

### PART 7 — Edge cases
Illiquid/thinly-traded stock → stale prices → **downward-biased** beta (Dimson correction
adds lagged terms). Recent IPO → insufficient history → your engine returns β = 1.

> **Learning mode — A3**
> Conceptual: (1) Why does the market not pay for idiosyncratic risk? (2) Raw vs adjusted vs
> bottom-up beta — when each? (3) What does a negative beta *mean* economically? (4) Why does
> leverage raise equity beta? (5) Why is low R² a problem for a regression beta?
> Numerical: (1) Cov(stock,mkt)=0.0009, Var(mkt)=0.0006 → β? (2) βU=0.9, D/E=1.0, t=25% →
> βL (Hamada)? (3) Rf 4%, ERP 5%, β 1.3 → Ke? β 0.6 → Ke? (4) Apply Blume: raw β 1.6 →
> adjusted? (5) β 1.0 fallback vs true β 1.4 — direction of valuation error?
> Trick: (1) "A company doubles its debt overnight — does its regression beta change today?
> Should its cost of equity?" (2) "Two firms, identical assets, different leverage — same or
> different equity beta?" (3) "Can a whole industry have β > 1? What does that imply for the
> market portfolio?"

---

## A4. Equity Risk Premium (ERP)

### PART 1 — Purpose
The ERP is the *extra* annual return equity investors demand over the risk-free rate for
bearing market risk. It's the price of risk itself. Every Ke and every WACC scales linearly
with it — it's the single most consequential *macro* assumption in the whole model.

### PART 3 — Why THIS value?
Your engine: **5.0% for mature markets, 6.5% for India** (5% base + **1.5% country risk
premium**), in `build_default_assumptions`.
- *Where 5% comes from*: it's the industry-standard mature-market ERP, roughly the midpoint
  of the three estimation schools (below). Damodaran's implied US ERP has hovered ~4.5–6%.
- *The +1.5% India CRP*: emerging markets carry additional political/economic/currency risk.
  Damodaran computes CRP from a country's default spread (sovereign CDS or rating-based
  spread) scaled by relative equity volatility. 1.5% is a reasonable India figure.
- *Is it fixed?* Hardcoded default, but editable per the AssumptionSet. *If ERP ↑*: Ke ↑,
  WACC ↑, value ↓ — and it hits high-beta names hardest (β multiplies ERP).

### PART 5 — Three ways professionals estimate ERP (know all three)
1. **Historical** (Ibbotson/Damodaran data): average realized stock-minus-bond return,
   1928–present. *Critique*: backward-looking, huge standard error, survivorship bias,
   depends on arithmetic vs geometric mean and the bond choice.
2. **Implied / forward-looking** (Damodaran's preferred): solve for the ERP that makes the
   PV of expected market cash flows equal the current index level — a "reverse DCF on the
   whole market." Market-consistent, updates daily. *Your 5% is best defended as a proxy for
   this.*
3. **Survey** (Fernandez): ask professors/analysts/CFOs. Behavioral, noisy, but a reality check.

### PART 6 — Interview defense
- Q: *"Where did 5% come from and is it arithmetic or geometric?"* → mature-market implied-ERP
  proxy; geometric is more appropriate for multi-period compounding/discounting, arithmetic
  for single-period expected return — say which and why.
- Q: *"Justify the India premium as exactly 1.5%."* → default-spread × relative-vol method;
  concede it's a round-number proxy for a Damodaran-style computed CRP.

> **Learning mode — A4**
> Conceptual: (1) Historical vs implied ERP — which is forward-looking? (2) Why is arithmetic
> mean > geometric mean, and which for DCF? (3) What is a country risk premium *made of*?
> (4) Why does ERP hit high-beta stocks hardest? (5) Why is the historical ERP's standard
> error so large? Numerical: (1) Ke with ERP 5% vs 6% at β 1.2, Rf 4%? (2) India Ke: Rf 7%,
> β 1.1, ERP 6.5%? Trick: (1) "If everyone used a lower ERP, what happens to market prices —
> and is that a bubble or rational?" (2) "Your implied ERP rises during a crash even as people
> feel *more* scared — reconcile that." (3) "Is the ERP a constant or does it move with
> sentiment? What does your hardcoded 5% assume?"

---

## A5. Cost of Equity (Ke) — CAPM

### PART 4 — Formula & derivation
```
Ke = Rf + β × ERP
```
- *Derivation*: CAPM says expected return on any asset = Rf + β×(E[Rm] − Rf), where
  (E[Rm] − Rf) is the ERP. It falls out of the assumption that investors hold the
  mean-variance-efficient market portfolio and price only systematic risk.
- *Worked example*: Rf 4.28%, β 1.04, ERP 5% → Ke = 4.28% + 1.04×5% = **9.48%**. (This is
  literally the number in your docs' WACC example.)

### PART 5 — Why CAPM and not the alternatives? (must-know comparison)
| Model | Adds | Pro | Con | Who uses it |
|---|---|---|---|---|
| **CAPM** (yours) | one factor (market) | simple, transparent, one β | empirically under-explains returns; ignores size/value/momentum | ~75% of practitioners, all IB/ER by default |
| **Fama-French 3/5** | size (SMB), value (HML), + profitability/investment | far better empirical fit | needs factor loadings + factor premia; unstable for one stock | academics, quant funds |
| **APT** | arbitrary macro factors | flexible | you must *choose* the factors — no theory says which | some macro/quant shops |
| **Build-up method** | Rf + ERP + size + company-specific premia | works for private/small firms with no β | subjective premia | valuation advisory / Big 4 for private co's |

**Interview line**: "I use CAPM as the transparent default because it needs only a
regression beta and a market premium, and it's what the counterparty on the other side of
a deal will use. For small/private names I'd switch to a build-up model; for a systematic
strategy, Fama-French." Your engine's docs even mention *optional* Fama-French 3/5 in the
quant layer — flag that as a strength.

### PART 6 — Interview defense
- Q: *"CAPM is empirically broken (Fama-French showed β alone doesn't explain returns) — why
  use it?"* → because it's the *lingua franca*: transparent, one estimable parameter, and
  deal counterparties, LBO models, and fairness opinions all speak it. The alternatives add
  precision at the cost of subjectivity and data. Valuation is about defensible consensus,
  not academic purity.

---

## A6. Cost of Debt (Kd) & the tax shield

### PART 3/4 — Why this value & formula
Your engine: **Kd = Interest Expense ÷ Total Debt**, clamped to **[1%, 15%]**; fallback
**Kd = Rf + 150bp** if interest/debt data is missing.
- *Why interest/debt*: it's the firm's *effective* borrowing cost from its own statements.
- *Why clamp [1%,15%]*: below 1% is a data error (interest or debt mis-scaled); above 15% is
  distressed/non-representative of *marginal* borrowing.
- *Why Rf + 150bp fallback*: 150bp ≈ an investment-grade credit spread — a reasonable default
  spread over the risk-free rate when you can't observe the firm's actual cost.
- **After-tax**: WACC uses `Kd × (1 − t)` because interest is **tax-deductible** — the "tax
  shield." Each dollar of interest saves `t` dollars of tax, so debt's *true* cost is lower
  than its coupon. This is the entire reason debt is "cheaper" than equity and why capital
  structure matters (Modigliani-Miller with taxes).

### PART 5 — Better alternatives
The *cleanest* Kd is **YTM on the firm's traded bonds** (market-based, forward-looking) or a
**synthetic rating** (interest-coverage → implied rating → default spread; Damodaran's
method) when bonds don't trade. Effective rate (yours) is *backward-looking* and mixes old
low-rate debt with new — flag this. Marginal > average cost of debt for valuation.

### PART 6 — Interview defense
- Q: *"You used the average historical interest rate — but valuation needs the *marginal* cost
  of new debt. Why?"* → concede: effective rate is a proxy; the theoretically correct figure
  is the YTM on new borrowing or a synthetic-rating spread. Defensible only when rates haven't
  moved much since the debt was issued.
- Q (trick): *"A firm with zero debt — what's its cost of debt and does it matter?"* → the
  Kd weight is zero, so Kd is irrelevant to WACC; WACC collapses to Ke.

---

## A7. WACC (Weighted Average Cost of Capital)

### PART 1 — Purpose
The blended required return of *all* capital providers, weighted by market value. It's the
correct discount rate for **FCFF** (which belongs to all providers). It's where cost of
equity, cost of debt, the tax shield, and capital structure all converge into one number.

### PART 4 — Formula
```
WACC = wE × Ke + wD × Kd × (1 − t)
       wE = E/(E+D),  wD = D/(E+D)   (market values)
```
- *Worked example (your docs)*: wE 0.943, Ke 9.48%, wD 0.057, Kd 4.10%, t 16.2% →
  WACC = 0.943×9.48% + 0.057×4.10%×(1−0.162) = **9.13%**.
- *Your engine's guard*: if market cap ≤ 0, weights are meaningless → it sets wE = 1 and
  discounts at Ke (WACC = Ke), and *says so* in the trace. Good practice: degrade transparently.

### PART 3 — Why market-value weights (not book)?
Because you're discounting for *today's* investors, who could sell at *market* prices. Book
equity is a historical-cost accounting residual, often wildly below market value → book
weights overweight debt → understate WACC → overvalue. **Common mistake: using book equity
in WACC weights.** Debt is often taken at book (acceptable proxy since debt trades near par
unless distressed).

### PART 5 — Why WACC/FCFF and not APV, FCFE, EVA, DDM?
This is the **"why not something else"** flagship comparison — memorize it:
- **APV (Adjusted Present Value)**: value the unlevered firm at Ku, then *add* the PV of tax
  shields separately. **Superior when leverage changes materially** (LBOs!) because WACC
  assumes a *constant* debt ratio. PE firms use APV for exactly this reason. Your engine uses
  WACC → implicitly assumes stable capital structure. *Concede this for LBO contexts.*
- **FCFE/Ke**: values equity directly; cleaner when leverage is stable or for financials.
  Should reconcile to WACC/FCFF's equity value — a good cross-check (your engine runs both).
- **EVA / Residual Income**: same value, different decomposition (highlights *economic profit*
  = spread over cost of capital). Your engine runs EVA as a consistency check on the DCF.
- **DDM**: only cash actually paid to shareholders; right for stable dividend payers/financials,
  wrong for retainers.

### PART 6 — Interview defense
- Q: *"WACC assumes a constant capital structure. When is that false, and what would you use
  instead?"* → LBOs / recaps / rapidly deleveraging firms; use **APV**. **This is the single
  most important WACC follow-up.**
- Q: *"Why do you tax-adjust only the debt, not the equity?"* → dividends aren't tax-deductible
  to the firm; interest is. The shield lives on the debt side.
- Q (trick): *"Adding debt lowers WACC (cheaper + shield). So is infinite debt optimal?"* → No
  — beyond a point, distress risk raises *both* Ke (higher equity risk) and Kd (higher spread),
  and the shield loses value if you can't use it. The WACC curve is U-shaped (trade-off theory).

> **Learning mode — A5–A7 (cost of capital block)**
> Conceptual: (1) Why discount FCFF at WACC but FCFE at Ke? (2) Why market-value weights?
> (3) Why is the WACC curve U-shaped? (4) When does APV beat WACC? (5) Why tax-shield only debt?
> Numerical: (1) E 9,430, D 570, Ke 9.48%, Kd 4.1%, t 16.2% → WACC? (2) All-equity firm, Ke 10%
> → WACC? (3) Firm moves from 0% to 40% debt, Kd 5%, t 25%, Ke rises 9%→11% — does WACC rise or
> fall? Compute both. (4) WACC 9%, terminal g 2.5% — terminal multiple 1/(WACC−g)? (5) If Ke 9.48%
> and market cap is 0 in your engine, what discount rate is used?
> Interview: (1) "Derive WACC from first principles." (2) "Your target has a bond yielding 7% but
> your effective Kd is 4% — which do you use and why?" (3) "Defend market over book weights to a
> skeptical CFO." (4) "Why might two banks compute different WACCs for the same target?"
> Trick: (1) "If debt is cheaper than equity, why doesn't every firm max out debt?" (2) "A firm
> buys back stock with debt — what happens to WACC in the short run vs long run?" (3) "Can WACC
> ever be below the risk-free rate?"

---

## A8. The DCF (FCFF) — your primary model

### PART 1 — Purpose
Your flagship intrinsic model (`app/domain/valuation/dcf.py`, weight **0.30** in the summary
— the highest). It converts a story about growth, margins, and reinvestment into a per-share
intrinsic value independent of what the market currently thinks. It exists to answer "what is
this *worth*, not what is it *priced* at."

### PART 4 — The full mechanic (formula + your assumptions)
For each forecast year t (default **5 years**):
```
Revenue_t   = Revenue_{t-1} × (1 + g_t)
EBIT_t      = Revenue_t × margin_t
NOPAT_t     = EBIT_t × (1 − t)
D&A_t       = Revenue_t × da_pct
CapEx_t     = Revenue_t × capex_pct   (fading toward D&A% by year N — steady state)
ΔNWC_t      = (Revenue_t − Revenue_{t-1}) × nwc_pct   (your default nwc_pct = 2%)
FCFF_t      = NOPAT_t + D&A_t − CapEx_t − ΔNWC_t
PV(FCFF_t)  = FCFF_t / (1 + WACC)^t
```
Then EV = ΣPV(FCFF) + PV(Terminal Value) (next section), bridged to equity.

**Why THESE default numbers (Part 3):**
- **Forecast horizon = 5 years** (10 for high-growth >15%): 5y is the industry standard —
  long enough to capture a transition to steady state, short enough that year-by-year
  forecasts remain credible. Beyond ~10y, forecasts are noise.
- **Revenue growth**: your engine seeds it from **3y/5y historical CAGR, clamped to [−5%, 30%]**,
  then **fades linearly to terminal growth**. *Fade* because no firm grows above GDP forever —
  competition and size drag returns to the mean (mean reversion). The clamp stops a single
  explosive/collapsing year from producing a nonsense perpetual growth path.
- **EBIT margin**: 3y average, held flat. Conservative — assumes no margin expansion you can't
  justify.
- **capex fades to D&A%**: in steady state, a firm only reinvests enough to maintain assets, so
  net capex ≈ depreciation. This prevents the terminal year from implying infinite free capex
  or infinite reinvestment.
- **ΔNWC = 2% of incremental revenue**: a generic working-capital intensity default; should
  ideally be derived from the firm's DSO/DIO/DPO. Flag as a simplification.

### PART 5 — Why not FCFE or a multiple here?
FCFF is preferred as the *primary* because it's capital-structure-neutral (WACC absorbs the
financing), so it's stable even if leverage drifts; FCFE requires modeling the debt schedule.
A multiple would import the market's current (possibly wrong) pricing — the DCF's whole point
is independence from that.

### PART 6 — Interview defense
- Q: *"80% of your value is in the terminal — so your 5-year forecast barely matters. Defend the
  DCF."* → the explicit period sets the *trajectory into* the terminal (terminal FCF and the
  growth/margin you fade to), so it matters more than the raw PV share suggests. But concede the
  DCF is a *terminal-value machine* and always cross-check with multiples.
- Q: *"Your revenue fades linearly to terminal growth — why linear, not an S-curve?"* → simplicity
  and transparency; concede an S-curve (slow, fast, mature) is more realistic for some businesses.
- Q (trick): *"Your terminal-year FCFF came out negative. What does your engine do and why is that
  correct?"* → it returns `not_applicable` with a reason — because a going-concern DCF with negative
  perpetual FCF is nonsense; you'd switch to multiples/RI or extend the horizon.

### PART 7 — Edge cases
Cyclical firm (auto, steel): a 3y-CAGR seed can catch a peak or trough → normalize over a full
cycle instead. Startup with negative EBIT: margin path must be *built up* to profitability, not
seeded from history — your engine's history-seeded defaults will fail here (honest limitation).

---

## A9. Terminal Value (Gordon vs Exit Multiple)

### PART 1 — Purpose
The value of *all* cash flows beyond the explicit forecast, collapsed into one number at year N.
It typically is **60–85% of total EV** (see the famous interview question). It exists because you
can't forecast to infinity, so you assume a steady state and use a perpetuity.

### PART 4 — Both methods (your engine computes both and cross-checks)
**Gordon Growth (perpetuity):**
```
TV_N = FCFF_N × (1 + g) / (WACC − g)
PV(TV) = TV_N / (1 + WACC)^N
```
- *Derivation*: sum of a growing perpetuity Σ FCFF_N(1+g)^k/(1+WACC)^k = FCFF_N(1+g)/(WACC−g).
- *Constraint your engine enforces*: **WACC > g**, else the formula is undefined/negative
  (infinite value). Your code returns `not_applicable` if WACC ≤ g. **Know why: you cannot grow
  a cash flow forever faster than the rate you discount it — the PV would be infinite.**

**Exit multiple (cross-check):** TV_N = EBITDA_N × (peer EV/EBITDA). Your engine PVs this too and
reports both so a wide divergence flags a bad assumption.

### PART 3 — Why terminal growth = 2.5% (US) / 5.0% (India)?
- **The cap: g ≤ long-run nominal GDP growth of the listing country.** Nothing outgrows the
  economy forever (or it *becomes* the economy). US long-run nominal GDP ≈ 2–2.5% real +
  inflation... your engine uses **2.5% for US** as a nominal-GDP proxy and **5.0% for India**
  (higher nominal GDP: higher real growth + higher inflation). A subtle but correct point: g
  should be a *nominal* growth rate because your cash flows are nominal.
- *If g ↑ toward WACC*: TV explodes (denominator → 0) — the model becomes hypersensitive. This is
  why your sensitivity grid varies g in tiny ±25bp steps.

### PART 5 — Gordon vs Exit Multiple vs Multi-stage vs H-Model
| Method | Assumes | Pro | Con | Preference |
|---|---|---|---|---|
| **Gordon** (yours) | one perpetual growth rate | pure intrinsic, internally consistent | hypersensitive to g near WACC; assumes instant steady state | academics, ER |
| **Exit multiple** (yours, as cross-check) | terminal sold at a market multiple | reality-anchored, quick | imports current market pricing → circular for an intrinsic model | IB, PE (LBO exits) |
| **Multi-stage** | explicit high → transition → stable | realistic for high-growth | more assumptions to defend | ER for growth names |
| **H-model** | growth *fades linearly* from high to stable | captures fade in closed form | approximation | Damodaran-style |

**Best-practice line**: "I compute Gordon *and* an exit-multiple TV and reconcile them — if they
diverge sharply, one of my assumptions (g, WACC, or the multiple) is wrong." Your engine does
exactly this — lead with it.

### PART 6 — Interview defense
- Q: *"Why is terminal value usually 70%+ of EV, and doesn't that make the DCF useless?"* →
  Because a perpetuity of stable cash flows is simply large relative to 5 discounted years; it's
  not a flaw, it reflects that most of a going concern's value is its long-run future. It's *not*
  useless because the explicit period *determines the terminal inputs* (the FCF base and the g/margin
  you converge to). But it *is* why you sanity-check TV with an exit multiple and report
  terminal-share-of-EV as a quality flag — which your engine does.
- Q (trick): *"Set g = WACC. What's the value and what does it mean?"* → infinite — economically
  meaningless; a business can't earn its cost of capital *and* grow forever without external
  capital. Your engine refuses this case.

> **Learning mode — A8–A9 (DCF + terminal block)**
> Conceptual: (1) Why must WACC > g? (2) Why cap g at nominal GDP? (3) Why nominal not real g?
> (4) Why does capex fade to D&A in the terminal year? (5) Why cross-check Gordon with an exit multiple?
> Numerical: (1) FCFF_5 = 600, g 2.5%, WACC 9% → TV_5? PV(TV) at N=5? (2) Terminal EBITDA 1,200,
> peer EV/EBITDA 8× → exit TV? (3) If g rises 2.5%→3.5% at WACC 9%, % change in TV? (4) Terminal
> share of EV if PV(TV)=4,000 and ΣPV(FCFF)=1,200? (5) WACC 6%, g 5.5% → TV multiplier 1/(WACC−g)?
> Interview: (1) "Walk me through building terminal value two ways." (2) "Your exit-multiple TV is
> 40% below your Gordon TV — what do you conclude?" (3) "Defend 2.5% as a US terminal growth rate."
> Trick: (1) "Can terminal growth be negative? When is that *correct*?" (2) "If I extend your
> forecast from 5 to 10 years with the same assumptions, does intrinsic value change? By how much,
> roughly, and why?" (3) "A firm's terminal FCF is negative — is the firm worthless?"

---

## A10. The EV → Equity Value bridge

### PART 4 — The bridge (your `dcf.py`)
```
Enterprise Value (EV) = ΣPV(FCFF) + PV(TV)
Equity Value = EV − Net Debt − Minority Interest  [− Preferred + Non-op investments]
Value per share = Equity Value / Diluted Shares
```
- *Net Debt = Total Debt − Cash*: debt holders have a senior claim, so subtract it; cash is
  already yours, so add it back (i.e. subtract *net* debt).
- *Minority interest*: subtract the portion of a consolidated subsidiary owned by *others* —
  it's in EV (you consolidated 100% of the sub's cash flows) but not yours.
- *Diluted* shares: include options/RSUs/convertibles because they're real claims on equity value.

### PART 6 — Interview defense
- Q: *"Why EV, not equity value, when you discount FCFF?"* → FCFF is cash to *all* providers, so
  discounting it gives the value of the *whole firm* (EV = debt + equity). You then *remove* the
  debt holders' claim (net debt) to isolate equity. Discounting FCFF and forgetting the bridge is
  the most common junior mistake.
- Q: *"Add back cash always?"* → operating cash needed to run the business isn't "excess" — purists
  net only *excess* cash. Your engine subtracts total cash (simplification).

---

## A11. FCFE DCF, DDM, Residual Income, EVA (the equity-side family)

**DCF-FCFE** (weight 0.15): FCFE = FCFF − after-tax interest (net borrowing = 0), discounted at
**Ke**. Lands on equity value directly. Preferred for stable-leverage and financial-adjacent names.
*Defense of net-borrowing=0*: it's the "constant debt policy" assumption; it overstates FCFE when a
firm is actively *raising* debt to fund growth (that debt is cash to equity your model omits).

**DDM** (weight 0.10): two-stage on dividends per share. Stage-1 growth from historical DPS CAGR,
**clamped [−5%, 15%]**, fading to terminal g, discounted at Ke. *Requires ≥3y dividend history →
else `not_applicable`.* Right for utilities, mature financials, consumer staples — anything that
pays a stable, meaningful dividend. Wrong for retainers (would value Amazon at ~0). The Gordon DDM
`P = D1/(Ke − g)` is the ancestor of all intrinsic valuation — know it cold.

**Residual Income** (weight 0.15): `V = BV0 + Σ PV[(ROE_t − Ke) × BV_{t−1}]`, ROE fading to Ke over
10y, clean-surplus book walk. *Intuition*: a firm is worth its book value *plus* the PV of returns
*above* its cost of equity. If ROE = Ke forever, the firm is worth exactly book — it's just
compensating for risk, creating no value. **Best for financials** (book value is economically
meaningful for banks; cash flow isn't). Also robust when most value is near-term (less
terminal-dependent than DCF).

**EVA / Economic Value Added** (weight 0.10): `V = IC0 + Σ PV[(ROIC_t − WACC) × IC_{t−1}]`, ROIC
fading to WACC. The enterprise-side twin of RI. *(ROIC − WACC)* is the **single most important
number in corporate finance** — positive spread = value creation, negative = destruction, growth
with a negative spread *destroys* value. Should reconcile to the FCFF DCF (your engine uses it as a
consistency check — mention this).

**Asset-Based** (weight 0.05): tangible book/share = (Equity − Goodwill − Intangibles)/shares. A
*floor*, not a going-concern value. For asset-heavy/deep-value/liquidation cases.

> **Interview one-liner tying it together**: "DCF-FCFF, FCFE, DDM, RI, and EVA are five windows onto
> the *same* intrinsic value — they differ in what cash flow they discount and at what rate, and in a
> perfect world with consistent assumptions they reconcile. I run several and weight by fit: EVA/DCF
> for industrials, RI/DDM for financials, and treat divergence as a signal to revisit assumptions."

---

## A12. Relative valuation — historical multiples & peer comps

### PART 1 — Purpose
Value inferred from what *comparable* assets trade for. Faster, market-anchored, and the *most-used*
method on the sell side. It answers "what's the market paying per unit of earnings/sales/EBITDA?"

### PART 4 — Which multiple is which (and the mechanic)
Your engine (`relative.py`):
- **Historical multiples** (weight 0.10): median of the company's *own* P/E, P/B, P/S history →
  applied to current EPS/BVPS/SPS. A mean-reversion bet on the company's own re-rating.
- **Peer comps** (weight 0.15): median of ≥3 peers' **P/E, P/B, P/S, EV/EBITDA**, IQR-trimmed, applied
  to the target. Requires ≥3 peers.

**[MULTIPLE TYPE — know equity vs enterprise multiples cold:]**
- **Equity multiples** (numerator = price/market cap): **P/E, P/B, P/S(equity), P/CF**. Contaminated
  by leverage — a levered and unlevered firm with identical operations have different P/Es.
- **Enterprise multiples** (numerator = EV): **EV/EBITDA, EV/Sales, EV/EBIT**. Capital-structure
  neutral — compare firms with different leverage cleanly. **Rule: EV multiples pair with pre-interest
  metrics (EBITDA, EBIT, Sales); equity multiples pair with post-interest metrics (net income, equity
  book, FCFE).** Mismatching them (e.g. EV/Net Income) is a classic error.

### PART 5 — Why comps, and why not *only* comps?
Comps require the fewest assumptions and reflect live market sentiment — but they inherit the market's
mispricing (if the whole sector is a bubble, your comp says "fairly valued" at bubble prices). DCF is
independent of that but assumption-heavy. **Use both: DCF for intrinsic truth, comps for market reality;
the gap between them is the thesis.**

### PART 6 — Interview defense
- Q: *"Why EV/EBITDA over P/E?"* → capital-structure and D&A-policy neutral; lets you compare across
  leverage and depreciation regimes. P/E is distorted by both.
- Q: *"Your peer set — how did you choose it and why does it matter more than the multiple?"* → comps
  live or die on comparability (same growth, margins, risk, capital intensity). A median of bad peers
  is precisely wrong. Your engine IQR-trims outliers — a partial defense.
- Q (trick): *"Two firms, same EV/EBITDA. One grows 20%, one 2%. Same value?"* → No — the grower
  deserves a higher multiple; raw comps ignore growth. That's why PEG (P/E ÷ growth) and
  regression-based comps (multiple vs growth+margin) exist. Your docs mention a regression option —
  cite it.

---

## A13. Reverse DCF, Scenarios, Monte Carlo, Sensitivity

**Reverse DCF** (`advanced.py`): fix value = market price, solve (bisection, 60 iters) for the implied
revenue growth. Answers *"what is the market assuming?"* — then compare to history. If the market prices
25% growth for a firm that's never exceeded 8%, that's a falsifiable, specific claim. **The single most
useful sanity check in practical investing** — lead with this in a stock-pitch interview.

**Scenarios** (bear/base/bull, **25/50/25%** probabilities): re-runs the full DCF with perturbed
growth/margin/terminal-g deltas, probability-weights the fair values, computes **margin of safety =
1 − price/weighted value**. *Why 25/50/25*: a symmetric, humble default — most weight on base, tails
acknowledged. Editable. MoS is the Graham/Buffett cushion against being wrong.

**Monte Carlo** (10,000 draws, **seed 42** for reproducibility): distributions — **growth ~ Normal(μ,
σ=max(0.4|μ|, 2%))**, **margin ~ Triangular(0.8μ, 1.15μ, μ)**, **WACC ~ Normal(σ=50bp)**, **terminal g
~ Uniform ±50bp** (bounded below WACC). Output: full fair-value distribution, P5–P95, and **P(value >
price)**. *Why distributions*: a point estimate hides the uncertainty; Monte Carlo turns "is it cheap?"
into "there's a 72% chance it's worth more than today's price." *Why Normal for growth, Triangular for
margin*: growth is roughly symmetric; margins have a most-likely value with bounded, skewed range.
*Why seed 42*: determinism — same inputs → same output, auditable. **Limitation to concede: it draws
inputs *independently*, ignoring correlation (high growth usually comes *with* margin pressure and higher
WACC). Correlated inputs would widen the distribution — a real weakness.**

**Sensitivity** (WACC × terminal-g grid): shows how fragile the point estimate is. *Why these two axes*:
the DCF is most sensitive to them, and near WACC ≈ g the value explodes — the grid makes that visible.

> **Learning mode — A12–A13**
> Conceptual: (1) Equity vs enterprise multiple — pair each with the right metric. (2) Why does comps
> inherit market mispricing? (3) What does reverse DCF *solve for*? (4) Why probability-weight scenarios
> instead of just using base? (5) Why is independent sampling a Monte Carlo weakness?
> Numerical: (1) EBITDA 500, peer EV/EBITDA 9×, net debt 800, shares 100 → implied price? (2) Bear 40,
> base 60, bull 90 at 25/50/25 → weighted value? MoS if price = 55? (3) Median peer P/E 15, EPS 4 →
> implied price? (4) P(value>price)=0.7 — how do you interpret it for a position size?
> Trick: (1) "Your reverse DCF implies 3% growth but the stock 'feels' expensive — is it?" (2) "Monte
> Carlo P50 equals your base DCF exactly — is that reassuring or suspicious?" (3) "A comp set of 3 peers,
> one at 40× and two at 12× — what does your IQR trim do, and is that right?"

---

## A14. Ratios & DuPont (~40 ratios, `ratios/engine.py`)

Ratios turn absolute figures into scale-free, comparable signals. Grouped:
- **Profitability**: gross/operating/net/EBITDA margin, ROE, ROA, **ROIC = NOPAT/Invested Capital**
  ("the moat metric" — compare to WACC), FCF margin.
- **Liquidity**: current, quick, cash ratios — survival over 12 months.
- **Leverage/coverage**: D/E, Net Debt/EBITDA (years to repay), interest coverage (EBIT/interest).
- **Efficiency**: asset turnover, DSO, DIO, DPO, **Cash Conversion Cycle = DSO + DIO − DPO** (days cash
  is trapped in operations; negative CCC = suppliers finance you, e.g. Amazon).
- **Market**: P/E, P/B, P/S, EV/EBITDA, EV/Sales, FCF yield, dividend yield.

**DuPont** — the "why is ROE what it is" decomposition:
```
3-step:  ROE = Net Margin × Asset Turnover × Financial Leverage
5-step:  ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Leverage
```
- *Purpose*: two firms with identical 20% ROE can be completely different — one earns it operationally
  (high margin × turnover), another through leverage (risky). DuPont exposes which. **Interview gold**:
  "A rising ROE driven by rising leverage, not margins, is a red flag, not a strength."

> **Learning mode — A14**: Conceptual: (1) Why is ROIC vs WACC the "value creation" test? (2) Why can a
> negative CCC be a competitive advantage? (3) Why decompose ROE? (4) High current ratio — always good?
> (5) Interest coverage of 1.5× — dangerous? Numerical: (1) NI 200, Rev 2,000, Assets 4,000, Equity 1,000
> → 3-step DuPont ROE? (2) DSO 45, DIO 60, DPO 90 → CCC? (3) EBIT 300, interest 100 → coverage? Trick:
> (1) "ROE rose from 12% to 18% — is that good?" (2) "A firm with ROIC 8% and WACC 10% doubles revenue —
> did it create value?" (3) "Quick ratio < 1 for Apple — is Apple in trouble?"

---

## A15. Diagnostic scores (`scores/classic.py`)

**Altman Z** (bankruptcy): weighted sum of 5 ratios. Your engine **auto-selects the variant** — original
Z (public manufacturer, uses market equity) vs **Z'' (non-manufacturer/EM, uses book equity)** — and
**refuses for financials** (leverage is their business model, not distress). *Zones*: distress / grey /
safe. Interview point: applying the manufacturer Z to a retailer or bank is a classic misuse.

**Piotroski F** (0–9 quality): 9 binary YoY tests across profitability (4), leverage/liquidity (3),
efficiency (2). Designed to separate winners from losers *within* cheap (high book-to-market) stocks —
a fundamental-quality overlay on a value screen.

**Beneish M** (earnings manipulation): 8 indices (DSRI, GMI, AQI, SGI, DEPI, SGAI, TATA, LVGI) × fixed
1999 coefficients, `M = −4.84 + Σ`. **M > −1.78 flags manipulation risk.** Famously flagged Enron before
collapse. Your engine imputes missing indices at neutral values but refuses if ≥4 of 8 are missing.

> **Learning mode — A15**: Conceptual: (1) Why does Altman need different variants? (2) Why exclude banks?
> (3) What is Piotroski *for* (not just what it measures)? (4) What behaviors leave "fingerprints" Beneish
> detects? (5) Why impute missing indices at neutral, and why refuse at ≥4 missing? Trick: (1) "A firm has
> a safe Altman Z but a flagging Beneish M — what's your read?" (2) "Piotroski 9/9 on an expensive growth
> stock — buy?" (3) "Can a healthy, fast-growing firm trip Beneish? Why?"

---

## A16. Factor scores (`scores/factors.py`)

Six pillars, 0–100, blended into a composite (default weights **Quality 25, Growth 20, Value 20,
Profitability 15, Momentum 10, Risk 10**):
- **Quality** (ROIC, margin stability, accruals, leverage), **Growth** (rev/NI/OCF CAGRs), **Value**
  (earnings yield, FCF yield, P/B), **Momentum** (6/12m return, % off 52w high), **Profitability**
  (margins, ROE), **Risk** (vol, drawdown, Altman — inverted so lower risk scores higher).
- *Theory*: the academic factor zoo (Fama-French + Carhart momentum + quality/profitability from
  Novy-Marx/Asness). These are the documented, persistent drivers of cross-sectional returns — the basis
  of smart-beta and quant equity. Your engine scores against absolute rubrics (transparent) rather than a
  black box.

> **Interview point**: "Value and momentum are *negatively correlated* factors — combining them diversifies.
> My composite weights reflect a quality-tilted, risk-aware default, all editable."

---

## A17. Quant / statistical layer (`quant/engine.py`)

Computed from price/return *time series*, not fundamentals:
- **Beta / Jensen's alpha / R²** — CAPM regression (feeds Ke).
- **Sharpe** = (R−Rf)/σ_total; **Sortino** = (R−Rf)/σ_downside (penalizes only bad vol); **Treynor** =
  (R−Rf)/β (for diversified holders); **Information Ratio** = active return/tracking error (skill vs a
  benchmark).
- **Max drawdown** (worst peak-to-trough — behaviorally what makes people sell the bottom); **Calmar** =
  return/|maxDD|.
- **VaR** (historical & parametric μ−1.645σ at 95%) — "worst expected loss at a confidence level";
  **CVaR/Expected Shortfall** — *average* loss beyond VaR (captures tail severity VaR ignores; CVaR is
  the more honest, coherent risk measure).
- **Rolling beta/Sharpe** — how risk evolves through time, not a static snapshot.

> **Learning mode — A16–A17**: Conceptual: (1) Sharpe vs Sortino vs Treynor — when each? (2) Why is CVaR
> "more honest" than VaR? (3) Why do value and momentum diversify? (4) What does Jensen's alpha isolate?
> (5) Why does max drawdown matter behaviorally beyond volatility? Numerical: (1) Return 12%, Rf 4%, σ 20%
> → Sharpe? (2) Same with downside σ 14% → Sortino? (3) 95% 1-day VaR from μ=0.05%, σ=1.5%? Trick:
> (1) "A fund has a great Sharpe but a −60% max drawdown — reconcile." (2) "VaR says you won't lose more
> than 3% at 95% — a client loses 15% — did VaR fail?" (3) "Can alpha be negative while returns are positive?"

---

# PART B — GLOBAL LAYER

## B1. (PART 8) How the Street actually does this

- **Investment Banking (M&A/ECM)**: DCF + comps + precedent transactions, presented as a **football
  field** (value range per method). WACC often a round number agreed with the team. Terminal value usually
  **exit-multiple** driven (they think in multiples). Heavy on comparable *transactions* (control premia).
  Your engine's football-field summary mirrors this.
- **Private Equity / LBO**: works *backwards* from a target IRR (~20–25%) and an exit multiple, solving for
  the entry price they can pay given a debt package. **APV or FCFE** (leverage changes drastically), not
  a static-WACC DCF. Obsessed with cash generation, debt paydown, and the exit.
- **Equity Research**: DCF + forward P/E / EV/EBITDA vs history and peers; publishes a **price target**
  (often 12-month, multiple-based) with a rating. Long, explicit models; frequent revisions on new data.
- **Big 4 / Valuation Advisory** (409A, PPA, impairment, fairness): rigorous, defensible,
  documentation-heavy; **build-up cost of equity** for private firms; size premia; DLOM/DLOC (discounts for
  lack of marketability/control). Regulated context — every number cited.
- **Hedge Funds**: reverse-DCF thinking ("what's priced in?"), variant perception vs consensus, scenario
  trees, catalysts. Less about a precise fair value, more about *asymmetry* and *mispricing*.
- **Corporate Finance (in-house)**: WACC for capital budgeting (NPV/IRR of projects), often a single
  corporate hurdle rate; capital structure and dividend policy.

**Universal shortcuts to know**: (1) mid-year convention (discount at t−0.5 — cash arrives through the
year, not at year-end) — **your engine does *not* use it; flag this**; (2) round-number WACC; (3) exit
multiple = current trading multiple; (4) normalize cyclicals over a cycle; (5) "haircut" management
projections (the "hockey stick" is always too optimistic).

## B2. (PART 10) What your project is MISSING — ranked by importance

1. **Bottom-up / unlevered (Hamada) beta & adjusted beta.** *(Highest — most likely interview hit.)* You
   use a raw 2y regression β. Add unlever/relever and a Blume adjustment. Enables private/IPO valuation and
   stabilizes β.
2. **Precedent Transactions & control premium.** IB's third pillar; you have comps but not deal comps. Also
   missing DLOM/DLOC discounts for private/control contexts.
3. **Mid-year discounting convention.** A ~half-period value uplift the Street assumes by default; its
   absence systematically *understates* your values slightly.
4. **APV / variable capital structure.** Your WACC assumes constant leverage — wrong for LBOs and
   deleveraging stories. Add an APV path.
5. **Correlated Monte Carlo inputs.** Independent draws understate tail risk; growth, margin, and WACC are
   correlated in reality.
6. **Normalized/mid-cycle earnings for cyclicals** and **explicit build-up path for pre-profit startups.**
   History-seeded defaults break for both.
7. **Sum-of-the-parts (SOTP)** for conglomerates; **excess vs operating cash** distinction in the bridge.
8. **Synthetic-rating cost of debt** (interest-coverage → spread) instead of backward-looking effective Kd.
9. **Currency/ADR handling** for multi-listed and cross-border names; explicit inflation-consistency checks.
10. **Sensitivity beyond WACC×g** (growth × margin, 2-factor tornado) and **explicit terminal-share-of-EV
    warnings surfaced in the UI**, not just computed.

## B3. (PART 11) The valuation knowledge graph

```
                        FINANCIAL STATEMENTS (10-K/10-Q, XBRL)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
   INCOME STMT                  BALANCE SHEET                 CASH FLOW STMT
   (Rev, EBIT, NI)          (Debt, Equity, Cash, IC)     (D&A, CapEx, ΔNWC, OCF)
        │                            │                            │
        └──────────────┬─────────────┴──────────────┬─────────────┘
                       ▼                             ▼
                    NOPAT = EBIT(1−t)          Net Debt, Invested Capital
                       │                             │
                       ▼                             │
        FCFF = NOPAT + D&A − CapEx − ΔNWC ◄──────────┘
             │                    │
             │                    └────► FCFE = FCFF − Int(1−t) + NetBorrow
             │                                   │
   ┌─────────┴─────────┐                         │
   ▼                   ▼                         ▼
 DISCOUNT RATE     TERMINAL VALUE            DISCOUNT AT Ke
   = WACC          (Gordon g ≤ nominal GDP           │
   │                OR exit multiple)                ▼
   │                   │                         DCF-FCFE, DDM, RI
   ▼                   │
 WACC = wE·Ke + wD·Kd·(1−t)                    ┌──── RATIOS ───┐
   │         │    │                            │  ROIC vs WACC │──► value creation
   │         │    └─ TAX SHIELD                │  DuPont ROE   │
   │         ▼                                 └───────────────┘
   │    Kd = Int/Debt (or Rf+150bp)
   ▼
 Ke = Rf + β × ERP  ◄─── CAPM
   │    │   │    │
   │    │   │    └─ ERP (5% mature / 6.5% India = 5% + 1.5% CRP)
   │    │   └────── BETA (2y OLS vs ^GSPC/^NSEI; →unlever/relever [MISSING])
   │    └────────── (β interacts with capital structure via Hamada)
   ▼
 Rf = 10Y govt yield (DGS10 / India 10Y; region + currency matched)
   │
   ▼
 ΣPV(FCFF) + PV(TV) = ENTERPRISE VALUE (EV)
   │
   ▼  − Net Debt − Minority Interest (− Preferred + Non-op assets)
 EQUITY VALUE
   │
   ▼  ÷ Diluted Shares
 INTRINSIC VALUE PER SHARE
   │
   ├──► vs MARKET PRICE ──► Reverse DCF (implied growth), Margin of Safety, Expected Return
   ├──► vs RELATIVE VAL (comps EV/EBITDA, P/E) ──► FOOTBALL FIELD (blended range)
   └──► MONTE CARLO / SCENARIOS ──► distribution, P(value>price)

  Parallel diagnostic rails (not in the DCF chain, but inform confidence):
   SCORES: Altman Z (distress) · Piotroski F (quality) · Beneish M (manipulation)
   FACTORS: Quality/Growth/Value/Momentum/Risk composite
   QUANT: β, Sharpe/Sortino/Treynor, VaR/CVaR, max drawdown
```

**How to read it in an interview**: "Everything flows from the statements to one number —
intrinsic value per share — through cash flow (numerator), the discount rate (denominator built
from Rf → β → ERP → CAPM → WACC), and the horizon (explicit + terminal). Then I triangulate that
against the market via multiples, reverse-DCF, and a probability distribution."

## B4. (PART 12) Consolidated exam — attempt before checking anything

**10 hardest conceptual:** (1) Why discount FCFF at WACC and FCFE at Ke — and why do they reconcile?
(2) Why must WACC > g, and what does WACC = g imply? (3) Why use market-value weights in WACC?
(4) When does APV beat WACC? (5) Why unlever beta? (6) Why is terminal value 70%+ of EV and why isn't
that a fatal flaw? (7) Equity vs enterprise multiples — pair each with its metric and say why. (8) Why is
(ROIC − WACC) the master value-creation test? (9) Why does a higher risk-free rate hurt growth stocks
most? (10) Why is CVaR more coherent than VaR?

**10 hardest numerical:** work every one in the per-topic learning blocks above; if you can't do them
cold, that topic isn't interview-ready.

**8 killer trick questions:** (1) "A firm with negative beta — is its cost of equity below the risk-free
rate, and is that *real*?" (2) "Set g = WACC. What's the value?" (3) "Add debt → WACC falls. Is infinite
debt optimal?" (4) "Your DCF and your comps disagree by 40%. Which is right?" (5) "Terminal growth of 5%
for India but 2.5% for the US — arbitrage that." (6) "Your Monte Carlo P50 exactly equals your base DCF —
good or suspicious?" (7) "ROE rose because leverage rose — bullish?" (8) "The market implies 3% growth via
your reverse DCF but consensus is 'expensive' — who's right?"

## B5. (PART 13) Defense scorecard & study roadmap

**How to self-grade (be honest — an interviewer will be):** for each dimension, can you (a) state the
theory from first principles, (b) write the formula and derive it, (c) defend *this project's* specific
number, and (d) survive two follow-ups? Three of four = 7/10; all four fluently = 9–10.

| Dimension | What "10/10" looks like | Where THIS project tests you |
|---|---|---|
| Financial Theory | Derive CAPM/Gordon/WACC from first principles | A0, A5, A7, A9 |
| Corporate Finance | APV vs WACC, capital structure, MM with taxes | A7, B1 |
| Accounting | Rebuild FCFF from 3 statements; clean-surplus; accruals | A1, A14, A15 |
| Valuation | Run + reconcile DCF, comps, RI, EVA; football field | A8–A13 |
| Discount-rate mastery | Defend Rf, β, ERP, Kd, weights, and every number | A2–A7 |
| Financial Modeling | Forecast drivers, fades, circularity, terminal | A8, A9, A13 |
| Business Understanding | Tie moats/cyclicality to assumptions | A8 P7, A15, B1 |
| Interview Readiness | Survive the trick questions in B4 | all P6/trick blocks |

**Roadmap — from "built a project" to "defends it before MDs and professors":**
1. **Weeks 1–2 (Foundations):** Master A0–A7 cold. Be able to derive CAPM and WACC on a whiteboard and
   defend every hardcoded number (Rf 10Y, β 2y-OLS, ERP 5%/6.5%, Kd clamp, tax clamp). Do all A1–A7
   learning drills. *Read: Damodaran, "Investment Valuation," Ch. 2–8; Koller (McKinsey) "Valuation," Ch. on cost of capital.*
2. **Weeks 3–4 (Intrinsic depth):** A8–A11. Build the DCF by hand in Excel, replicate your engine's
   output, then break it (negative FCF, g→WACC). Learn Hamada unlever/relever and *add it* to close your
   biggest gap. Learn APV and when to switch. *Read: Damodaran Ch. 12–15; McKinsey Ch. on continuing value.*
3. **Weeks 5–6 (Relative + market):** A12–A13. Master equity-vs-enterprise multiple pairing, build a comp
   set, run a reverse DCF on a real stock and defend the implied growth. Learn precedent transactions +
   control premia (your biggest *missing* method). *Read: Rosenbaum & Pearl, "Investment Banking," comps + precedents chapters.*
4. **Weeks 7–8 (Diagnostics + quant + polish):** A14–A17. Then drill B4's trick questions until fluent, and
   do a live mock defense of the whole knowledge graph (B3) end-to-end. Fill the top-5 items in B2 (bottom-up
   beta, precedents/DLOM, mid-year convention, APV, correlated MC) so you can say "I know the limitation and
   here's the fix" for each. *Read: CFA Level II Equity Valuation readings; Piotroski (2000) and Beneish (1999) original papers.*

**Golden rule for the interview:** never defend a number as "correct" — defend it as *reasonable, sourced,
and editable*, then immediately name the better method and when you'd switch. That posture — knowing the
limitation before they raise it — is what separates a candidate who *used* a model from one who *understands*
it.
