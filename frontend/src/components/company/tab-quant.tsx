"use client";
/** Quant desk: performance ratios (formulas on hover), VaR block, rolling
 *  beta / Sharpe series from real return calculations. */
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { EmptyState, Panel, PanelHeader, Reveal, Skeleton } from "@/components/ui/primitives";
import { useQuantPerformance, useQuantRisk, useQuantRolling } from "@/hooks/use-api";
import { pct } from "@/lib/format";
import { cn } from "@/lib/utils";

export function QuantTab({ id }: { id: string }) {
  return (
    <div className="space-y-4">
      <Reveal><PerformancePanel id={id} /></Reveal>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Reveal delay={0.06}><RiskPanel id={id} /></Reveal>
        <Reveal delay={0.1} className="lg:col-span-2"><RollingPanel id={id} /></Reveal>
      </div>
    </div>
  );
}

function PerformancePanel({ id }: { id: string }) {
  const { data, isLoading, error } = useQuantPerformance(id);
  if (isLoading) return <Panel><Skeleton className="m-4 h-24" /></Panel>;
  if (error || !data) {
    return <Panel><EmptyState title="Insufficient price history"
                              detail="Quant metrics need ≥60 trading sessions." /></Panel>;
  }
  const m = data.data.metrics;
  const cells: { label: string; value: string; cls?: string; formula?: string }[] = [
    { label: "Ann. return", value: pct(m.annualized_return),
      cls: m.annualized_return >= 0 ? "text-up" : "text-down" },
    { label: "Volatility", value: pct(m.annualized_volatility) },
    { label: "Beta", value: m.beta?.toFixed(2) ?? "—",
      formula: "OLS on daily log returns vs benchmark" },
    { label: "Sharpe", value: m.sharpe?.toFixed(2) ?? "—", formula: m.formulas.sharpe },
    { label: "Sortino", value: m.sortino?.toFixed(2) ?? "—", formula: m.formulas.sortino },
    { label: "Treynor", value: m.treynor?.toFixed(3) ?? "—", formula: m.formulas.treynor },
    { label: "Jensen α", value: m.jensen_alpha !== null ? pct(m.jensen_alpha) : "—",
      cls: (m.jensen_alpha ?? 0) >= 0 ? "text-up" : "text-down",
      formula: m.formulas.jensen_alpha },
    { label: "Info ratio", value: m.information_ratio?.toFixed(2) ?? "—",
      formula: m.formulas.information_ratio },
    { label: "Tracking err", value: m.tracking_error !== null ? pct(m.tracking_error) : "—",
      formula: m.formulas.tracking_error },
    { label: "Max drawdown", value: pct(m.max_drawdown), cls: "text-down",
      formula: m.formulas.max_drawdown },
    { label: "Calmar", value: m.calmar?.toFixed(2) ?? "—", formula: m.formulas.calmar },
  ];
  return (
    <Panel>
      <PanelHeader
        title="Performance & factor metrics"
        right={
          <span className="font-mono text-[10px] text-faint">
            3y window · vs {data.data.benchmark} · rf {pct(data.data.risk_free_rate.value)}{" "}
            ({data.data.risk_free_rate.source})
          </span>
        }
      />
      <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-4 lg:grid-cols-6">
        {cells.map((c) => (
          <div key={c.label} className="bg-surface px-4 py-3" title={c.formula}>
            <div className="label">{c.label}</div>
            <div className={cn("tnum mt-1 font-mono text-sm font-semibold", c.cls)}>{c.value}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RiskPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useQuantRisk(id);
  if (isLoading) return <Panel><Skeleton className="m-4 h-40" /></Panel>;
  if (error || !data) return <Panel><EmptyState title="Risk metrics unavailable" /></Panel>;
  const r = data.data;
  const rows = [
    { label: "VaR 95% (hist.)", value: r.var_95_hist },
    { label: "VaR 99% (hist.)", value: r.var_99_hist },
    { label: "VaR 95% (param.)", value: r.var_95_parametric },
    { label: "CVaR 95% (ES)", value: r.cvar_95 },
    { label: "CVaR 99% (ES)", value: r.cvar_99 },
  ];
  const maxAbs = Math.max(...rows.map((x) => Math.abs(x.value)));
  return (
    <Panel className="h-full">
      <PanelHeader title="Value at risk — daily" />
      <div className="space-y-3 p-4">
        {rows.map((row) => (
          <div key={row.label}>
            <div className="flex items-baseline justify-between text-[11px]">
              <span className="text-muted">{row.label}</span>
              <span className="tnum font-mono font-semibold text-down">{pct(row.value)}</span>
            </div>
            <div className="mt-1 h-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-down/70"
                style={{ width: `${(Math.abs(row.value) / maxAbs) * 100}%` }}
              />
            </div>
          </div>
        ))}
        <div className="border-t border-line pt-3 text-[11px] text-muted">
          Annualized volatility{" "}
          <span className="tnum float-right font-mono text-fg">{pct(r.annualized_volatility)}</span>
        </div>
      </div>
    </Panel>
  );
}

function RollingPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useQuantRolling(id);
  if (isLoading) return <Panel><Skeleton className="m-4 h-56" /></Panel>;
  if (error || !data) return <Panel><EmptyState title="Rolling series unavailable" /></Panel>;

  const merged = new Map<string, { date: string; beta?: number; sharpe?: number }>();
  for (const b of data.data.rolling_beta) {
    merged.set(b.date, { date: b.date, beta: b.beta });
  }
  for (const s of data.data.rolling_sharpe) {
    merged.set(s.date, { ...(merged.get(s.date) ?? { date: s.date }), sharpe: s.sharpe });
  }
  const rows = [...merged.values()].sort((a, b) => a.date.localeCompare(b.date));

  return (
    <Panel className="h-full">
      <PanelHeader title={`Rolling beta & Sharpe (${data.data.window_days}d window)`} />
      <div className="h-[260px] p-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--grid-line)" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                   minTickGap={70} tickLine={false} axisLine={false}
                   tickFormatter={(d: string) =>
                     new Date(d).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} />
            <YAxis orientation="right" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                   tickLine={false} axisLine={false} width={40} />
            <Tooltip
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
                    <div className="text-faint">{label as string}</div>
                    {payload.map((p) => (
                      <div key={p.dataKey as string} className="tnum mt-0.5 flex justify-between gap-4 font-mono">
                        <span className="text-muted">{String(p.name)}</span>
                        <span>{(p.value as number)?.toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
            />
            <ReferenceLine y={1} stroke="var(--border-strong)" strokeDasharray="4 3" />
            <Line type="monotone" dataKey="beta" name="β" stroke="var(--accent)"
                  dot={false} strokeWidth={1.5} animationDuration={700} connectNulls />
            <Line type="monotone" dataKey="sharpe" name="Sharpe" stroke="var(--up)"
                  dot={false} strokeWidth={1.5} animationDuration={900} connectNulls />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
