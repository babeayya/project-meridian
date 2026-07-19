"use client";
/** Valuation desk: DCF playground with editable assumptions, football field,
 *  waterfall, sensitivity heatmap, Monte Carlo distribution — all live runs
 *  against the engine, every result carrying its full audit trace. */
import { BoltIcon, PlayIcon } from "@heroicons/react/24/outline";
import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";

import { TraceView } from "@/components/company/trace-view";
import {
  Badge, Button, ConfidenceMeter, CountUp, EmptyState, Panel, PanelHeader, Reveal, Skeleton,
} from "@/components/ui/primitives";
import {
  useAssumptions, useBridge, useMcDistribution, useRunValuation, useSensitivity, useWaterfall,
} from "@/hooks/use-api";
import { MODEL_LABELS, type SensitivityGrid, type ValuationOutcome } from "@/lib/api";
import { compact, currencySymbol, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ValuationTab({ id }: { id: string }) {
  return (
    <div className="space-y-4">
      <Reveal><DcfPlayground id={id} /></Reveal>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Reveal delay={0.05}><FootballField id={id} /></Reveal>
        <Reveal delay={0.1}><Waterfall id={id} /></Reveal>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Reveal delay={0.12}><SensitivityPanel id={id} /></Reveal>
        <Reveal delay={0.16}><MonteCarloPanel id={id} /></Reveal>
      </div>
    </div>
  );
}

/* ── DCF playground ─────────────────────────────────────────────────────── */

function DcfPlayground({ id }: { id: string }) {
  const { data: assumptions, isLoading, error } = useAssumptions(id);
  const run = useRunValuation(id);
  const [outcome, setOutcome] = useState<ValuationOutcome | null>(null);
  const [showTrace, setShowTrace] = useState(false);

  // editable overrides (percent units in UI, decimals to the API)
  const [growth, setGrowth] = useState<number | null>(null);
  const [margin, setMargin] = useState<number | null>(null);
  const [terminalG, setTerminalG] = useState<number | null>(null);

  const a = assumptions?.data.assumptions;
  const baseGrowth = a ? parseFloat(a.revenue_growth[0]) * 100 : 0;
  const baseMargin = a ? parseFloat(a.ebit_margin[0]) * 100 : 0;
  const baseTerminal = a ? parseFloat(a.terminal_growth) * 100 : 0;

  const execute = async (model = "dcf-fcff") => {
    const overrides: Record<string, unknown> = {};
    if (a && growth !== null && Math.abs(growth - baseGrowth) > 0.01) {
      const g0 = growth / 100;
      const gt = (terminalG ?? baseTerminal) / 100;
      const n = a.revenue_growth.length;
      overrides.revenue_growth = Array.from({ length: n }, (_, i) =>
        (g0 + ((gt - g0) * i) / n).toFixed(4));
    }
    if (a && margin !== null && Math.abs(margin - baseMargin) > 0.01) {
      overrides.ebit_margin = a.ebit_margin.map(() => (margin / 100).toFixed(4));
    }
    if (terminalG !== null && Math.abs(terminalG - baseTerminal) > 0.01) {
      overrides.terminal_growth = (terminalG / 100).toFixed(4);
    }
    const res = await run.mutateAsync({
      model, overrides: Object.keys(overrides).length ? overrides : undefined,
    });
    setOutcome(res.data);
  };

  if (error) {
    return (
      <Panel>
        <EmptyState
          title="Assumptions unavailable"
          detail="The engine derives defaults from fundamentals — ingest them first (header → Refresh data)."
        />
      </Panel>
    );
  }

  const fair = outcome?.fair_value_per_share ? parseFloat(outcome.fair_value_per_share) : null;

  return (
    <Panel>
      <PanelHeader
        title="DCF playground"
        right={a && (
          <span className="text-[10px] text-faint" title={assumptions?.data.derivation.wacc}>
            rf {pct(a.wacc.risk_free_rate)} ({a.wacc.rf_source}) · β {parseFloat(a.wacc.beta).toFixed(2)} ·
            WACC {assumptions?.data.derivation.wacc?.split(" — ")[0]
              ? pct(assumptions.data.derivation.wacc.split(" — ")[0]) : "—"} ·
            {" "}{a.forecast_years}y explicit forecast, terminal from year {a.forecast_years + 1}
          </span>
        )}
      />
      {isLoading || !a ? (
        <div className="grid grid-cols-3 gap-4 p-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 p-5 lg:grid-cols-[1fr_300px]">
          <div className="space-y-5">
            <AssumptionSlider
              label="Year-1 revenue growth" value={growth ?? baseGrowth}
              base={baseGrowth} min={-10} max={40}
              onChange={setGrowth}
              derivation={assumptions.data.derivation.revenue_growth}
            />
            <AssumptionSlider
              label="EBIT margin" value={margin ?? baseMargin}
              base={baseMargin} min={1} max={60}
              onChange={setMargin}
              derivation={assumptions.data.derivation.ebit_margin}
            />
            <AssumptionSlider
              label="Terminal growth" value={terminalG ?? baseTerminal}
              base={baseTerminal} min={0} max={6} step={0.1}
              onChange={setTerminalG}
              derivation={assumptions.data.derivation.terminal_growth}
            />
            <div className="flex items-center gap-2 pt-1">
              <Button variant="primary" onClick={() => execute()} disabled={run.isPending}>
                <PlayIcon className="h-3.5 w-3.5" />
                {run.isPending ? "Pricing…" : "Run DCF (FCFF)"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => { setGrowth(null); setMargin(null); setTerminalG(null); }}
              >
                Reset to derived
              </Button>
            </div>
          </div>

          <div className="flex flex-col justify-center rounded-xl border border-line bg-surface-2 p-5">
            {run.isPending ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-9 w-36" />
                <Skeleton className="h-3 w-28" />
              </div>
            ) : outcome ? (
              outcome.status === "ok" && fair !== null ? (
                <>
                  <span className="label">Fair value / share</span>
                  <CountUp
                    value={fair}
                    format={(n) => `${currencySymbol(outcome.currency)}${n.toFixed(2)}`}
                    className="mt-1 font-mono text-3xl font-semibold text-accent"
                  />
                  {outcome.low && outcome.high && (
                    <span className="tnum mt-1 font-mono text-xs text-muted">
                      range {currencySymbol(outcome.currency)}{parseFloat(outcome.low).toFixed(2)}
                      {" – "}{currencySymbol(outcome.currency)}{parseFloat(outcome.high).toFixed(2)}
                    </span>
                  )}
                  <div className="mt-3 flex items-center justify-between">
                    <span className="label">Confidence</span>
                    <ConfidenceMeter value={outcome.confidence} />
                  </div>
                  <button
                    onClick={() => setShowTrace((v) => !v)}
                    className="mt-3 text-left text-[11px] text-accent hover:underline"
                  >
                    {showTrace ? "Hide" : "Show"} full calculation trace →
                  </button>
                </>
              ) : (
                <>
                  <Badge tone="warn">NOT APPLICABLE</Badge>
                  <p className="mt-2 text-xs leading-relaxed text-muted">
                    {outcome.not_applicable_reason}
                  </p>
                </>
              )
            ) : (
              <>
                <BoltIcon className="h-5 w-5 text-faint" />
                <p className="mt-2 text-xs text-muted">
                  Adjust assumptions and run — the engine re-prices with a complete
                  formula-level audit trail.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      <AnimatePresence>
        {showTrace && outcome?.trace && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-line"
          >
            <div className="max-h-[460px] overflow-y-auto p-4">
              <TraceView node={outcome.trace} />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Panel>
  );
}

function AssumptionSlider({
  label, value, base, min, max, step = 0.5, onChange, derivation,
}: {
  label: string; value: number; base: number; min: number; max: number;
  step?: number; onChange: (v: number) => void; derivation?: string;
}) {
  const changed = Math.abs(value - base) > 0.01;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="label" title={derivation}>{label}</span>
        <span className={cn("tnum font-mono text-sm font-medium", changed && "text-accent")}>
          {value.toFixed(1)}%
          {changed && (
            <span className="ml-1.5 text-[10px] text-faint">base {base.toFixed(1)}%</span>
          )}
        </span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="mt-2 w-full accent-[var(--accent)]"
        aria-label={label}
      />
      {derivation && (
        <p className="mt-1 truncate text-[10px] text-faint" title={derivation}>{derivation}</p>
      )}
    </div>
  );
}

/* ── football field ─────────────────────────────────────────────────────── */

function FootballField({ id }: { id: string }) {
  const { data, isLoading, error } = useBridge(id);
  const models = data?.data.models ?? [];
  const price = data?.data.price ? parseFloat(data.data.price) : null;

  const domain = useMemo(() => {
    const values = models.flatMap((m) => [
      parseFloat(m.fair_value),
      m.low ? parseFloat(m.low) : NaN,
      m.high ? parseFloat(m.high) : NaN,
    ]).filter(isFinite);
    if (price) values.push(price);
    if (!values.length) return [0, 1] as const;
    const lo = Math.min(...values), hi = Math.max(...values);
    const pad = (hi - lo) * 0.08 || 1;
    return [lo - pad, hi + pad] as const;
  }, [models, price]);

  const pos = (v: number) => ((v - domain[0]) / (domain[1] - domain[0])) * 100;

  return (
    <Panel>
      <PanelHeader
        title="Valuation bridge — football field"
        right={data?.data.skipped.length ? (
          <span className="text-[10px] text-faint" title={data.data.skipped
            .map((s) => `${MODEL_LABELS[s.model] ?? s.model}: ${s.reason}`).join("\n")}>
            {data.data.skipped.length} model(s) not applicable
          </span>
        ) : undefined}
      />
      {isLoading ? (
        <div className="space-y-2 p-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-6" />)}</div>
      ) : error || models.length === 0 ? (
        <EmptyState title="No stored valuation runs" detail="Run a model in the playground above." />
      ) : (
        <div className="relative p-4 pr-6">
          {price !== null && (
            <div
              className="absolute bottom-3 top-3 z-10 w-px border-l border-dashed border-fg/50"
              style={{ left: `calc(${pos(price)}% )` }}
            >
              <span className="absolute -top-1 left-1 whitespace-nowrap font-mono text-[9px] text-muted">
                price {currencySymbol(data!.data.currency)}{price.toFixed(0)}
              </span>
            </div>
          )}
          <div className="space-y-2.5 pt-3">
            {models.map((m, i) => {
              const fv = parseFloat(m.fair_value);
              const lo = m.low ? parseFloat(m.low) : fv;
              const hi = m.high ? parseFloat(m.high) : fv;
              return (
                <div key={m.model} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 truncate text-[11px] text-muted">
                    {MODEL_LABELS[m.model] ?? m.model}
                  </span>
                  <div className="relative h-5 flex-1">
                    <motion.div
                      className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-accent/25"
                      initial={{ width: 0, left: `${pos(lo)}%` }}
                      animate={{ width: `${Math.max(pos(hi) - pos(lo), 0.5)}%`, left: `${pos(lo)}%` }}
                      transition={{ duration: 0.6, delay: i * 0.05 }}
                    />
                    <motion.div
                      className="absolute top-1/2 h-3 w-[3px] -translate-y-1/2 rounded-full bg-accent"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1, left: `${pos(fv)}%` }}
                      transition={{ duration: 0.5, delay: i * 0.05 + 0.2 }}
                      title={`${currencySymbol(data!.data.currency)}${fv.toFixed(2)}`}
                    />
                  </div>
                  <span className="tnum w-16 shrink-0 text-right font-mono text-[11px]">
                    {currencySymbol(data!.data.currency)}{fv.toFixed(0)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Panel>
  );
}

/* ── DCF waterfall ──────────────────────────────────────────────────────── */

function Waterfall({ id }: { id: string }) {
  const { data, isLoading, error } = useWaterfall(id);
  const blocks = data?.data.blocks ?? [];
  const bars = blocks
    .filter((b) => b.type !== "result" && b.value)
    .map((b) => ({ name: b.label, value: Math.abs(parseFloat(b.value)), type: b.type }));

  return (
    <Panel>
      <PanelHeader
        title="DCF waterfall"
        right={data?.data.terminal_share_of_ev != null && (
          <Badge tone={data.data.terminal_share_of_ev > 0.8 ? "warn" : "neutral"}>
            terminal {Math.round(data.data.terminal_share_of_ev * 100)}% of EV
          </Badge>
        )}
      />
      {isLoading ? (
        <Skeleton className="m-4 h-[240px]" />
      ) : error || bars.length === 0 ? (
        <EmptyState title="No DCF run stored" detail="Run the DCF playground first." />
      ) : (
        <div className="h-[260px] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={bars} margin={{ top: 8, right: 8, bottom: 24, left: 0 }}>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: "var(--text-faint)" }}
                     interval={0} angle={-18} textAnchor="end"
                     tickLine={false} axisLine={false} />
              <YAxis orientation="right" tickFormatter={(v: number) => compact(v, 0)}
                     tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} width={52} />
              <Tooltip
                cursor={{ fill: "var(--grid-line)" }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
                      {(payload[0].payload as { name: string }).name}:{" "}
                      <span className="tnum font-mono">
                        {currencySymbol(data!.data.currency)}{compact(payload[0].value as number)}
                      </span>
                    </div>
                  ) : null}
              />
              <Bar dataKey="value" radius={[3, 3, 0, 0]} animationDuration={700}>
                {bars.map((b, i) => (
                  <Cell
                    key={i}
                    fill={b.type === "subtract" ? "var(--down)"
                      : b.type === "subtotal" ? "var(--accent)" : "var(--up)"}
                    fillOpacity={b.type === "subtotal" ? 0.9 : 0.65}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}

/* ── sensitivity heatmap ────────────────────────────────────────────────── */

function SensitivityPanel({ id }: { id: string }) {
  const sensitivity = useSensitivity(id);
  const [grid, setGrid] = useState<SensitivityGrid | null>(null);

  const load = async () => setGrid((await sensitivity.mutateAsync()).data);

  const values = grid?.grid.matrix.flat().filter((v): v is string => v !== null)
    .map(parseFloat) ?? [];
  const lo = Math.min(...values), hi = Math.max(...values);
  const priceNum = grid?.current_price ? parseFloat(grid.current_price) : null;

  return (
    <Panel>
      <PanelHeader
        title="Sensitivity — WACC × terminal growth"
        right={
          <Button variant="ghost" onClick={load} disabled={sensitivity.isPending}>
            <PlayIcon className="h-3 w-3" />
            {sensitivity.isPending ? "Computing…" : grid ? "Recompute" : "Compute"}
          </Button>
        }
      />
      {!grid ? (
        sensitivity.isPending
          ? <Skeleton className="m-4 h-[220px]" />
          : <EmptyState title="Grid not computed" detail="5×5 fair values around the base case." />
      ) : (
        <div className="overflow-x-auto p-4">
          <table className="w-full border-collapse text-center font-mono text-[11px]">
            <thead>
              <tr>
                <th className="p-1.5 text-left text-[9px] font-normal text-faint">g ↓ / WACC →</th>
                {grid.grid.x_values.map((x) => (
                  <th key={x} className="tnum p-1.5 font-semibold text-muted">{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grid.grid.matrix.map((row, ri) => (
                <tr key={ri}>
                  <td className="tnum p-1.5 text-left font-semibold text-muted">
                    {grid.grid.y_values[ri]}
                  </td>
                  {row.map((cell, ci) => {
                    const v = cell !== null ? parseFloat(cell) : null;
                    const t = v !== null && hi > lo ? (v - lo) / (hi - lo) : 0.5;
                    const abovePrice = v !== null && priceNum !== null && v >= priceNum;
                    return (
                      <td
                        key={ci}
                        className={cn("tnum p-1.5 transition-transform hover:scale-[1.06]",
                          abovePrice && "font-semibold")}
                        style={{
                          background: v === null ? undefined
                            : `color-mix(in srgb, var(--up) ${Math.round(t * 34)}%, var(--surface-2))`,
                        }}
                        title={abovePrice ? "above current market price" : undefined}
                      >
                        {v !== null ? v.toFixed(0) : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {priceNum !== null && (
            <div className="mt-2 text-right text-[10px] text-faint">
              bold = fair value ≥ current price ({priceNum.toFixed(0)})
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

/* ── Monte Carlo distribution ───────────────────────────────────────────── */

function MonteCarloPanel({ id }: { id: string }) {
  const { data, isLoading, error, refetch } = useMcDistribution(id);
  const run = useRunValuation(id);
  const mc = data?.data;
  const priceNum = mc?.price_at_run ? parseFloat(mc.price_at_run) : null;

  const runMc = async () => {
    await run.mutateAsync({ model: "monte-carlo-dcf" });
    refetch();
  };

  return (
    <Panel>
      <PanelHeader
        title="Monte Carlo DCF distribution"
        right={mc && (
          <span className="tnum font-mono text-[10px] text-faint">
            {mc.iterations.toLocaleString()} seeded paths · P(V&gt;price){" "}
            {mc.prob_above_price !== null ? pct(mc.prob_above_price) : "—"}
          </span>
        )}
      />
      {isLoading ? (
        <Skeleton className="m-4 h-[220px]" />
      ) : error || !mc ? (
        <EmptyState
          title="No simulation stored"
          action={
            <Button variant="primary" onClick={runMc} disabled={run.isPending}>
              <PlayIcon className="h-3.5 w-3.5" />
              {run.isPending ? "Simulating 10,000 paths…" : "Run Monte Carlo"}
            </Button>
          }
        />
      ) : (
        <div className="h-[250px] p-2">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={mc.histogram} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={1}>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis dataKey="bin_low" tick={{ fontSize: 9, fill: "var(--text-faint)" }}
                     tickFormatter={(v: number) => v.toFixed(0)} minTickGap={30}
                     tickLine={false} axisLine={false} />
              <YAxis orientation="right" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} width={40} />
              <Tooltip
                cursor={{ fill: "var(--grid-line)" }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
                      {(payload[0].payload as { bin_low: number }).bin_low.toFixed(1)}–
                      {(payload[0].payload as { bin_high: number }).bin_high.toFixed(1)}:{" "}
                      <span className="tnum font-mono">{payload[0].value as number} paths</span>
                    </div>
                  ) : null}
              />
              {priceNum !== null && (
                <ReferenceLine x={nearestBin(mc.histogram, priceNum)} stroke="var(--down)"
                               strokeDasharray="4 3"
                               label={{ value: "price", fontSize: 9, fill: "var(--down)" }} />
              )}
              <ReferenceLine x={nearestBin(mc.histogram, mc.percentiles.p50)} stroke="var(--accent)"
                             strokeDasharray="4 3"
                             label={{ value: "P50", fontSize: 9, fill: "var(--accent)" }} />
              <Bar dataKey="count" fill="var(--accent)" fillOpacity={0.55}
                   animationDuration={700} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {mc && (
        <div className="grid grid-cols-5 gap-px border-t border-line bg-line">
          {(["p5", "p25", "p50", "p75", "p95"] as const).map((p) => (
            <div key={p} className="bg-surface px-3 py-2 text-center">
              <div className="label">{p.toUpperCase()}</div>
              <div className="tnum mt-0.5 font-mono text-xs">
                {currencySymbol(mc.currency)}{mc.percentiles[p]?.toFixed(0)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function nearestBin(hist: { bin_low: number }[], v: number): number | undefined {
  if (!hist.length) return undefined;
  let best = hist[0].bin_low, dist = Infinity;
  for (const b of hist) {
    const d = Math.abs(b.bin_low - v);
    if (d < dist) { dist = d; best = b.bin_low; }
  }
  return best;
}
