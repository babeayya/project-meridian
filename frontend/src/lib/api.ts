/** Typed client for the Equity Research backend. Every call returns the
 *  backend envelope { data, meta } — no fabricated values anywhere. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000/api/v1";

export interface Meta {
  sources: string[];
  freshness: Record<string, unknown>;
  warnings: string[];
}
export interface Envelope<T> {
  data: T;
  meta: Meta;
}

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, title: string, detail: string) {
    super(`${title}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<Envelope<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let title = res.statusText, detail = "";
    try {
      const body = await res.json();
      title = body.title ?? title;
      detail = body.detail ?? "";
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, title, detail);
  }
  return res.json();
}

export const get = <T>(path: string) => request<T>(path);
export const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : "{}" });

/** Health endpoints return bare JSON without the {data, meta} envelope. */
export async function getRaw<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new ApiError(res.status, res.statusText, "");
  return res.json();
}

/* ---------- domain types (mirror backend schemas) ---------- */

export interface Listing {
  id: string;
  ticker: string;
  exchange: string;
  yahoo_symbol: string | null;
  currency: string | null;
  is_primary: boolean;
}
export interface CompanyProfile {
  id: string;
  name: string;
  country: string;
  sector: string | null;
  industry: string | null;
  website: string | null;
  description: string | null;
  reporting_currency: string | null;
  listings: Listing[];
}
export interface ResolveCandidate {
  company_id: string | null;
  name: string;
  ticker: string;
  exchange: string;
  symbol: string;
  region: string;
  confidence: number;
  provider: string;
}
export interface ResolveResponse {
  match: CompanyProfile | null;
  candidates: ResolveCandidate[];
}

export interface PricePoint {
  date: string;
  open: string | null;
  high: string | null;
  low: string | null;
  close: string;
  adj_close: string | null;
  volume: number | null;
}
export interface PriceSeries {
  listing_id: string;
  ticker: string;
  exchange: string;
  currency: string | null;
  points: PricePoint[];
}
export interface Quote {
  listing_id: string;
  ticker: string;
  price: string;
  currency: string | null;
  change_pct: string | null;
  market_cap: string | null;
  as_of: string;
  source: string;
}

export interface LineItem {
  label: string;
  value: string;
  statement: string;
}
export interface StatementPeriod {
  fiscal_year: number;
  period_end: string;
  currency: string;
  source: string;
  items: Record<string, LineItem>;
}
export interface Financials {
  period_type: string;
  periods: StatementPeriod[];
}

export interface CalcInput {
  name: string;
  symbol: string;
  value: string;
  unit: string;
  confidence: number;
  source?: { provider: string } | null;
}
export interface CalcNode {
  key: string;
  label: string;
  formula: string;
  substitution: string;
  result: string;
  unit: string;
  explanation: string;
  assumptions: string[];
  confidence: number;
  inputs: CalcInput[];
  intermediates: CalcNode[];
}
export interface RatiosResponse {
  as_of: string;
  currency: string;
  groups: Record<string, Record<string, CalcNode>>;
}

export interface ScoreResult {
  score_type: string;
  value: string;
  grade: string;
  components: Record<string, unknown>[];
  not_applicable_reason?: string | null;
}
export interface FactorScore {
  pillar: string;
  score: number;
  coverage: number;
  components: { metric: string; value: unknown; score: number | null; rubric: string }[];
}
export interface ScoresResponse {
  classic: {
    altman_z: ScoreResult | null;
    piotroski_f: ScoreResult | null;
    beneish_m: ScoreResult | null;
  };
  factors: Record<string, FactorScore>;
  composite: FactorScore;
}

export interface ValuationOutcome {
  model: string;
  status: string;
  not_applicable_reason: string | null;
  fair_value_per_share: string | null;
  currency: string;
  low: string | null;
  high: string | null;
  confidence: number;
  outputs: Record<string, unknown>;
  trace: CalcNode | null;
  run_id?: string;
}
export interface FootballFieldEntry {
  model: string;
  fair_value: string;
  low: string | null;
  high: string | null;
  confidence: number;
  weight: number;
}
export interface ValuationSummary {
  football_field: FootballFieldEntry[];
  skipped: { model: string; reason: string }[];
  blended: {
    fair_value: number;
    range_low: number;
    range_high: number;
    price?: number;
    upside_pct?: number;
    margin_of_safety?: number;
  } | null;
}
export interface SensitivityGrid {
  grid: {
    x_var: string;
    y_var: string;
    x_values: string[];
    y_values: string[];
    matrix: (string | null)[][];
  };
  current_price: string | null;
}
export interface Assumptions {
  assumptions: {
    forecast_years: number;
    revenue_growth: string[];
    ebit_margin: string[];
    tax_rate: string;
    da_pct_revenue: string;
    capex_pct_revenue: string;
    nwc_pct_revenue_delta: string;
    terminal_growth: string;
    shares_diluted: string;
    net_debt: string;
    wacc: {
      risk_free_rate: string;
      beta: string;
      equity_risk_premium: string;
      rf_source: string;
      beta_source: string;
    };
  };
  derivation: Record<string, string>;
}

export interface QuantPerformance {
  metrics: {
    window_days: number;
    annualized_return: number;
    annualized_volatility: number;
    sharpe: number | null;
    sortino: number | null;
    treynor: number | null;
    jensen_alpha: number | null;
    information_ratio: number | null;
    tracking_error: number | null;
    max_drawdown: number;
    calmar: number | null;
    beta: number | null;
    formulas: Record<string, string>;
  };
  risk_free_rate: { value: string; source: string };
  benchmark: string;
}
export interface QuantRisk {
  var_95_hist: number;
  var_99_hist: number;
  var_95_parametric: number;
  cvar_95: number;
  cvar_99: number;
  annualized_volatility: number;
}
export interface QuantRolling {
  rolling_beta: { date: string; beta: number }[];
  rolling_sharpe: { date: string; sharpe: number }[];
  window_days: number;
}

export interface NewsAnalysis {
  sentiment: "positive" | "neutral" | "negative";
  sentiment_score: number;
  confidence: number;
  importance: number;
  category: string | null;
  expected_impact: string | null;
  method: string;
}
export interface NewsArticle {
  id: string;
  headline: string;
  url: string;
  outlet: string | null;
  provider: string;
  published_at: string | null;
  analysis: NewsAnalysis | null;
}

export interface AiAnalysis {
  agent: string;
  output: Record<string, unknown>;
  model: string;
  confidence: number | null;
  tokens: { in: number | null; out: number | null };
  created_at: string;
}

export interface WaterfallChart {
  run_id: string;
  currency: string;
  blocks: { label: string; value: string; type: string }[];
  terminal_share_of_ev: number | null;
  ev: string;
}
export interface BridgeChart {
  price: string | null;
  currency: string;
  models: {
    model: string;
    fair_value: string;
    low: string | null;
    high: string | null;
    confidence: number;
    upside_pct: number | null;
  }[];
  skipped: { model: string; reason: string }[];
}
export interface McDistribution {
  currency: string;
  price_at_run: string | null;
  iterations: number;
  mean: number;
  percentiles: Record<string, number>;
  prob_above_price: number | null;
  histogram: { bin_low: number; bin_high: number; count: number }[];
}
export interface MarginsChart {
  years: number[];
  gross: (number | null)[];
  operating: (number | null)[];
  net: (number | null)[];
}
export interface FinancialHistoryChart {
  currency: string;
  years: number[];
  series: Record<string, (string | null)[]>;
}
export interface RadarScores {
  axes: { pillar: string; score: number; coverage: number }[];
  composite: number;
}
export interface SentimentTimeline {
  timeline: { date: string; avg_sentiment: number; count: number }[];
}
export interface ProviderHealth {
  providers: {
    provider: string;
    capabilities: string[];
    breaker: string;
    rate_limit: { per_minute: number; per_day: number | null };
  }[];
}

export const VALUATION_MODELS = [
  "dcf-fcff", "dcf-fcfe", "ddm", "residual-income", "eva", "asset-based",
  "multiples", "scenario", "monte-carlo-dcf", "reverse-dcf", "expected-return",
] as const;

export const MODEL_LABELS: Record<string, string> = {
  dcf_fcff: "DCF (FCFF)",
  dcf_fcfe: "DCF (FCFE)",
  ddm: "Dividend Discount",
  residual_income: "Residual Income",
  eva: "Economic Value Added",
  asset_based: "Asset Based",
  multiples: "Historical Multiples",
  comps: "Peer Comps",
  scenario: "Scenario Weighted",
  monte_carlo_dcf: "Monte Carlo DCF",
  reverse_dcf: "Reverse DCF",
  expected_return: "Expected Return",
};
