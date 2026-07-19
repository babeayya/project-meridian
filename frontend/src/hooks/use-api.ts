"use client";
/** React Query hooks over the backend API. Query keys are stable and
 *  cache-scoped per company; live quote polls on an interval. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api";
import { get, getRaw, post } from "@/lib/api";

export function useResolve(query: string, enabled = true) {
  return useQuery({
    queryKey: ["resolve", query],
    queryFn: () => post<api.ResolveResponse>("/companies/resolve", { query }),
    enabled: enabled && query.trim().length >= 2,
    staleTime: 5 * 60_000,
  });
}

export function useSelectCandidate() {
  return useMutation({
    mutationFn: (candidate: api.ResolveCandidate) =>
      post<api.CompanyProfile>("/companies/resolve/select", candidate),
  });
}

export function useCompany(id: string) {
  return useQuery({
    queryKey: ["company", id],
    queryFn: () => get<api.CompanyProfile>(`/companies/${id}`),
    staleTime: 10 * 60_000,
  });
}

export function useQuote(id: string, poll = true) {
  return useQuery({
    queryKey: ["quote", id],
    queryFn: () => get<api.Quote>(`/companies/${id}/quote`),
    refetchInterval: poll ? 30_000 : false,
    staleTime: 15_000,
  });
}

export function usePrices(id: string, range: string) {
  return useQuery({
    queryKey: ["prices", id, range],
    queryFn: () => get<api.PriceSeries>(`/companies/${id}/prices?range=${range}`),
    staleTime: 5 * 60_000,
  });
}

export function useFinancials(id: string, period: "annual" | "quarterly") {
  return useQuery({
    queryKey: ["financials", id, period],
    queryFn: () =>
      get<api.Financials>(`/companies/${id}/financials?statement=all&period=${period}&limit=12`),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useRefreshFundamentals(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<unknown>(`/companies/${id}/fundamentals/refresh`),
    onSuccess: () => qc.invalidateQueries(),
  });
}

export function useRatios(id: string) {
  return useQuery({
    queryKey: ["ratios", id],
    queryFn: () => get<api.RatiosResponse>(`/companies/${id}/ratios`),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useDupont(id: string) {
  return useQuery({
    queryKey: ["dupont", id],
    queryFn: () => get<api.CalcNode>(`/companies/${id}/ratios/dupont`),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useScores(id: string) {
  return useQuery({
    queryKey: ["scores", id],
    queryFn: () => get<api.ScoresResponse>(`/companies/${id}/scores`),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useAssumptions(id: string) {
  return useQuery({
    queryKey: ["assumptions", id],
    queryFn: () => get<api.Assumptions>(`/companies/${id}/assumptions`),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

export function useRunValuation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ model, overrides }: { model: string; overrides?: Record<string, unknown> }) =>
      post<api.ValuationOutcome>(`/companies/${id}/valuations/${model}`,
        overrides ? { overrides } : {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["waterfall", id] });
      qc.invalidateQueries({ queryKey: ["bridge", id] });
      qc.invalidateQueries({ queryKey: ["mc", id] });
    },
  });
}

export function useValuationSummary(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ["valuation-summary", id],
    queryFn: () => get<api.ValuationSummary>(`/companies/${id}/valuations/summary`),
    enabled,
    staleTime: 30 * 60_000,
    retry: false,
  });
}

export function useSensitivity(id: string) {
  return useMutation({
    mutationFn: () => post<api.SensitivityGrid>(`/companies/${id}/valuations/sensitivity`),
  });
}

export function useQuantPerformance(id: string) {
  return useQuery({
    queryKey: ["quant-perf", id],
    queryFn: () => get<api.QuantPerformance>(`/companies/${id}/quant/performance?window=3y`),
    staleTime: 30 * 60_000,
    retry: false,
  });
}

export function useQuantRisk(id: string) {
  return useQuery({
    queryKey: ["quant-risk", id],
    queryFn: () => get<api.QuantRisk>(`/companies/${id}/quant/risk`),
    staleTime: 30 * 60_000,
    retry: false,
  });
}

export function useQuantRolling(id: string) {
  return useQuery({
    queryKey: ["quant-rolling", id],
    queryFn: () => get<api.QuantRolling>(`/companies/${id}/quant/rolling`),
    staleTime: 30 * 60_000,
    retry: false,
  });
}

export function useNews(id: string) {
  return useQuery({
    queryKey: ["news", id],
    queryFn: () => get<{ articles: api.NewsArticle[] }>(`/companies/${id}/news?limit=60&days=60`),
    staleTime: 5 * 60_000,
  });
}

export function useRefreshNews(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => post<unknown>(`/companies/${id}/news/refresh?lookback_days=14`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["news", id] });
      qc.invalidateQueries({ queryKey: ["sentiment", id] });
    },
  });
}

export function useSentimentTimeline(id: string) {
  return useQuery({
    queryKey: ["sentiment", id],
    queryFn: () => get<api.SentimentTimeline>(`/companies/${id}/news/sentiment-timeline?days=90`),
    staleTime: 5 * 60_000,
  });
}

export function useAiAnalyses(id: string) {
  return useQuery({
    queryKey: ["ai", id],
    queryFn: () => get<{ analyses: api.AiAnalysis[]; available_agents: string[] }>(
      `/companies/${id}/ai/analyses`),
    staleTime: 60_000,
  });
}

/** Runs ONE agent per request. The full suite takes ~18 min on free models,
 *  so the UI drives agents sequentially (see tab-ai) — each request stays short,
 *  partial results stream in, and one failure never loses the others. */
export function useRunAgent(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (agent: string) =>
      post<{ completed: string[]; errors: Record<string, string> }>(
        `/companies/${id}/ai/analyze`, { agents: [agent] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ai", id] }),
  });
}

/* chart-shaped endpoints */
export const useWaterfall = (id: string) =>
  useQuery({
    queryKey: ["waterfall", id],
    queryFn: () => get<api.WaterfallChart>(`/charts/${id}/dcf-waterfall`),
    staleTime: 60_000, retry: false,
  });
export const useBridge = (id: string) =>
  useQuery({
    queryKey: ["bridge", id],
    queryFn: () => get<api.BridgeChart>(`/charts/${id}/valuation-bridge`),
    staleTime: 60_000, retry: false,
  });
export const useMcDistribution = (id: string) =>
  useQuery({
    queryKey: ["mc", id],
    queryFn: () => get<api.McDistribution>(`/charts/${id}/monte-carlo-distribution`),
    staleTime: 60_000, retry: false,
  });
export const useMargins = (id: string) =>
  useQuery({
    queryKey: ["margins", id],
    queryFn: () => get<api.MarginsChart>(`/charts/${id}/margins`),
    staleTime: 10 * 60_000, retry: false,
  });
export const useFinancialHistory = (id: string, metrics: string) =>
  useQuery({
    queryKey: ["fin-history", id, metrics],
    queryFn: () =>
      get<api.FinancialHistoryChart>(`/charts/${id}/financial-history?metrics=${metrics}`),
    staleTime: 10 * 60_000, retry: false,
  });
export const useRadar = (id: string) =>
  useQuery({
    queryKey: ["radar", id],
    queryFn: () => get<api.RadarScores>(`/charts/${id}/radar-scores`),
    staleTime: 10 * 60_000, retry: false,
  });
export const useProviderHealth = () =>
  useQuery({
    queryKey: ["providers"],
    queryFn: () => getRaw<api.ProviderHealth>("/health/providers"),
    staleTime: 60_000, retry: false,
  });
