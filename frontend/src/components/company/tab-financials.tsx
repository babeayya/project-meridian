"use client";
/** Excel-grade statement viewer: annual/quarterly toggle, statement filter,
 *  sticky first column + header, YoY delta coloring, row search, CSV export. */
import { ArrowDownTrayIcon, ArrowPathIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { useMemo, useState } from "react";

import { Badge, Button, EmptyState, Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { useFinancials, useRefreshFundamentals } from "@/hooks/use-api";
import { compact } from "@/lib/format";
import { cn, downloadCsv } from "@/lib/utils";

const STATEMENTS = [
  { key: "all", label: "All" },
  { key: "income", label: "Income" },
  { key: "balance", label: "Balance Sheet" },
  { key: "cashflow", label: "Cash Flow" },
] as const;

// keys where an increase is a cash cost, not an improvement
const INVERTED = new Set(["capex", "short_term_debt", "long_term_debt", "total_liabilities"]);

export function FinancialsTab({ id }: { id: string }) {
  const [period, setPeriod] = useState<"annual" | "quarterly">("annual");
  const [statement, setStatement] = useState<string>("all");
  const [search, setSearch] = useState("");
  const { data, isLoading, error } = useFinancials(id, period);
  const refresh = useRefreshFundamentals(id);

  const periods = useMemo(() => data?.data.periods ?? [], [data]);

  // union of line-item keys across periods, grouped by statement
  const rows = useMemo(() => {
    const keys = new Map<string, { label: string; statement: string }>();
    for (const p of periods) {
      for (const [k, item] of Object.entries(p.items)) {
        if (!keys.has(k)) keys.set(k, { label: item.label, statement: item.statement });
      }
    }
    let list = [...keys.entries()].map(([key, v]) => ({ key, ...v }));
    if (statement !== "all") list = list.filter((r) => r.statement === statement);
    if (search) list = list.filter((r) =>
      r.label.toLowerCase().includes(search.toLowerCase()));
    const order = { income: 0, cashflow: 1, balance: 2, other: 3 } as Record<string, number>;
    list.sort((a, b) => (order[a.statement] ?? 3) - (order[b.statement] ?? 3));
    return list;
  }, [periods, statement, search]);

  const exportCsv = () =>
    downloadCsv(`financials-${period}.csv`, [
      ["line_item", "statement", ...periods.map((p) => `FY${p.fiscal_year}`)],
      ...rows.map((r) => [
        r.label, r.statement,
        ...periods.map((p) => p.items[r.key]?.value ?? ""),
      ]),
    ]);

  if (error) {
    return (
      <Panel>
        <EmptyState
          title="No statements ingested for this company yet"
          detail="Pull fundamentals through the provider chain (SEC EDGAR → Yahoo → FMP)."
          action={
            <Button variant="primary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
              <ArrowPathIcon className={cn("h-3.5 w-3.5", refresh.isPending && "animate-spin")} />
              {refresh.isPending ? "Ingesting…" : "Ingest fundamentals"}
            </Button>
          }
        />
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader
        title={
          <span className="flex items-center gap-2">
            Financial statements
            {data && (
              <Badge tone="neutral">
                {data.meta.sources.join(", ")} · {periods[0]?.currency}
              </Badge>
            )}
          </span>
        }
        right={
          <div className="no-print flex items-center gap-2">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-faint" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Filter line items"
                className="w-36 rounded-md border border-line bg-surface-2 py-1 pl-6 pr-2 text-[11px] outline-none placeholder:text-faint focus:border-accent/40"
              />
            </div>
            <div className="flex overflow-hidden rounded-md border border-line">
              {(["annual", "quarterly"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-medium capitalize transition-colors",
                    period === p ? "bg-accent/15 text-accent" : "text-muted hover:text-fg",
                  )}
                >
                  {p}
                </button>
              ))}
            </div>
            <button onClick={exportCsv} className="p-1 text-muted hover:text-fg" title="Export CSV">
              <ArrowDownTrayIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        }
      />

      <div className="no-print flex gap-1 border-b border-line px-3 py-2">
        {STATEMENTS.map((s) => (
          <button
            key={s.key}
            onClick={() => setStatement(s.key)}
            className={cn(
              "rounded px-2 py-0.5 text-[11px] transition-colors",
              statement === s.key ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
            )}
          >
            {s.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="space-y-1.5 p-4">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-7" />)}
        </div>
      ) : (
        <div className="max-h-[620px] overflow-auto">
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 z-10">
              <tr className="bg-surface">
                <th className="sticky left-0 z-20 min-w-[220px] border-b border-r border-line bg-surface px-3 py-2 text-left">
                  <span className="label">Line item</span>
                </th>
                {periods.map((p) => (
                  <th key={p.period_end} className="border-b border-line px-3 py-2 text-right">
                    <div className="font-mono text-[11px] font-semibold">
                      {period === "annual" ? `FY${p.fiscal_year}` : p.period_end.slice(0, 7)}
                    </div>
                    <div className="text-[9px] font-normal text-faint">{p.source}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, ri) => (
                <tr
                  key={r.key}
                  className={cn(
                    "group border-b border-line transition-colors last:border-0 hover:bg-surface-2",
                    ri > 0 && rows[ri - 1].statement !== r.statement && "border-t-2 border-t-line-strong",
                  )}
                >
                  <td className="sticky left-0 z-10 border-r border-line bg-surface px-3 py-1.5 group-hover:bg-surface-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn("h-1 w-1 rounded-full",
                          r.statement === "income" ? "bg-accent"
                          : r.statement === "cashflow" ? "bg-up" : "bg-warn")}
                        title={r.statement}
                      />
                      {r.label}
                    </div>
                  </td>
                  {periods.map((p, pi) => {
                    const cur = p.items[r.key]?.value;
                    const prev = pi > 0 ? periods[pi - 1].items[r.key]?.value : undefined;
                    const delta = yoy(cur, prev);
                    return (
                      <td
                        key={p.period_end}
                        className="tnum px-3 py-1.5 text-right font-mono"
                        title={delta !== null
                          ? `${delta > 0 ? "+" : ""}${(delta * 100).toFixed(1)}% vs prior`
                          : undefined}
                      >
                        <span>{cur ? compact(cur) : <span className="text-faint">—</span>}</span>
                        {delta !== null && Math.abs(delta) > 0.001 && (
                          <span
                            className={cn("ml-1.5 text-[9px]",
                              (INVERTED.has(r.key) ? delta < 0 : delta > 0)
                                ? "text-up" : "text-down")}
                          >
                            {delta > 0 ? "▲" : "▼"}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <EmptyState title="No line items match the filter" />}
        </div>
      )}
    </Panel>
  );
}

function yoy(cur?: string, prev?: string): number | null {
  if (!cur || !prev) return null;
  const c = parseFloat(cur), p = parseFloat(prev);
  if (!isFinite(c) || !isFinite(p) || p === 0) return null;
  return (c - p) / Math.abs(p);
}
