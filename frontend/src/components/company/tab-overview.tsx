"use client";
/** Overview: price chart, factor radar, revenue/income history, margins,
 *  latest classified headlines. */
import {
  PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer,
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, Tooltip, XAxis, YAxis,
} from "recharts";

import { PriceChart } from "@/components/company/price-chart";
import { Badge, EmptyState, Panel, PanelHeader, Reveal, Skeleton } from "@/components/ui/primitives";
import { useFinancialHistory, useMargins, useNews, useRadar } from "@/hooks/use-api";
import type { CompanyProfile } from "@/lib/api";
import { compact, pct, relTime } from "@/lib/format";

export function OverviewTab({ id, company }: { id: string; company: CompanyProfile }) {
  const listing = company.listings.find((l) => l.is_primary) ?? company.listings[0];

  return (
    <div className="space-y-4">
      <Reveal>
        <PriceChart id={id} currency={listing?.currency ?? company.reporting_currency} />
      </Reveal>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Reveal delay={0.05}><RadarPanel id={id} /></Reveal>
        <Reveal delay={0.1} className="lg:col-span-2"><HistoryPanel id={id} /></Reveal>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Reveal delay={0.12}><MarginsPanel id={id} /></Reveal>
        <Reveal delay={0.16}><HeadlinesPanel id={id} /></Reveal>
      </div>

      {company.description && (
        <Reveal delay={0.2}>
          <Panel className="p-4">
            <div className="label">About</div>
            <p className="mt-2 max-w-3xl text-xs leading-relaxed text-muted">
              {company.description}
            </p>
          </Panel>
        </Reveal>
      )}
    </div>
  );
}

function RadarPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useRadar(id);
  return (
    <Panel className="h-full">
      <PanelHeader
        title="Factor profile"
        right={data && <Badge tone="accent">Composite {data.data.composite}</Badge>}
      />
      <div className="h-[260px] p-2">
        {isLoading ? <Skeleton className="h-full w-full" /> : error ? (
          <EmptyState title="Scores unavailable" detail="Refresh fundamentals first." />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={data!.data.axes} outerRadius="72%">
              <PolarGrid stroke="var(--grid-line)" />
              <PolarAngleAxis
                dataKey="pillar"
                tick={{ fontSize: 10, fill: "var(--text-muted)" }}
              />
              <Radar
                dataKey="score"
                stroke="var(--accent)"
                fill="var(--accent)"
                fillOpacity={0.18}
                animationDuration={700}
              />
              <Tooltip
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
                      {(payload[0].payload as { pillar: string }).pillar}:{" "}
                      <span className="tnum font-mono">{payload[0].value as number}</span>/100
                    </div>
                  ) : null
                }
              />
            </RadarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}

function HistoryPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useFinancialHistory(
    id, "revenue,net_income,operating_cash_flow");
  const rows = data
    ? data.data.years.map((y, i) => ({
        year: y,
        revenue: numOrNull(data.data.series.revenue?.[i]),
        net_income: numOrNull(data.data.series.net_income?.[i]),
        ocf: numOrNull(data.data.series.operating_cash_flow?.[i]),
      }))
    : [];
  return (
    <Panel className="h-full">
      <PanelHeader title={`Fundamentals history ${data ? `(${data.data.currency})` : ""}`} />
      <div className="h-[260px] p-2">
        {isLoading ? <Skeleton className="h-full w-full" /> : error ? (
          <EmptyState title="No fundamentals ingested" detail="Use Refresh data in the header." />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} />
              <YAxis orientation="right" tickFormatter={(v: number) => compact(v, 0)}
                     tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} width={52} />
              <Tooltip
                cursor={{ fill: "var(--grid-line)" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-xl">
                      <div className="text-faint">FY{label as number}</div>
                      {payload.map((p) => (
                        <div key={p.dataKey as string} className="tnum mt-0.5 flex justify-between gap-4 font-mono">
                          <span className="text-muted">{String(p.name)}</span>
                          <span>{compact(p.value as number)}</span>
                        </div>
                      ))}
                    </div>
                  ) : null
                }
              />
              <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
              <Bar dataKey="revenue" name="Revenue" fill="var(--accent)" radius={[2, 2, 0, 0]}
                   animationDuration={600} fillOpacity={0.85} />
              <Bar dataKey="net_income" name="Net income" fill="var(--up)" radius={[2, 2, 0, 0]}
                   animationDuration={800} fillOpacity={0.85} />
              <Bar dataKey="ocf" name="Op. cash flow" fill="var(--warn)" radius={[2, 2, 0, 0]}
                   animationDuration={1000} fillOpacity={0.7} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}

function MarginsPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useMargins(id);
  const rows = data
    ? data.data.years.map((y, i) => ({
        year: y,
        gross: scaled(data.data.gross[i]),
        operating: scaled(data.data.operating[i]),
        net: scaled(data.data.net[i]),
      }))
    : [];
  return (
    <Panel>
      <PanelHeader title="Margin structure" />
      <div className="h-[220px] p-2">
        {isLoading ? <Skeleton className="h-full w-full" /> : error ? (
          <EmptyState title="No margin history" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis dataKey="year" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} />
              <YAxis orientation="right" tickFormatter={(v: number) => `${v}%`}
                     tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} width={44} />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-xl">
                      <div className="text-faint">FY{label as number}</div>
                      {payload.map((p) => (
                        <div key={p.dataKey as string} className="tnum mt-0.5 flex justify-between gap-4 font-mono">
                          <span className="text-muted">{String(p.name)}</span>
                          <span>{(p.value as number)?.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  ) : null
                }
              />
              <Legend wrapperStyle={{ fontSize: 10 }} iconSize={8} />
              <Line type="monotone" dataKey="gross" name="Gross" stroke="var(--accent)"
                    dot={false} strokeWidth={1.5} animationDuration={700} />
              <Line type="monotone" dataKey="operating" name="Operating" stroke="var(--up)"
                    dot={false} strokeWidth={1.5} animationDuration={900} />
              <Line type="monotone" dataKey="net" name="Net" stroke="var(--warn)"
                    dot={false} strokeWidth={1.5} animationDuration={1100} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}

function HeadlinesPanel({ id }: { id: string }) {
  const { data, isLoading } = useNews(id);
  const articles = (data?.data.articles ?? []).slice(0, 5);
  return (
    <Panel>
      <PanelHeader title="Latest headlines" />
      {isLoading ? (
        <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-8" />)}</div>
      ) : articles.length === 0 ? (
        <EmptyState title="No news ingested yet" detail="Open the News tab and refresh." />
      ) : (
        <div className="divide-y divide-line">
          {articles.map((a) => (
            <a
              key={a.id}
              href={a.url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-surface-2"
            >
              <SentimentDot sentiment={a.analysis?.sentiment} />
              <span className="min-w-0 flex-1 truncate text-xs">{a.headline}</span>
              <span className="shrink-0 text-[10px] text-faint">{relTime(a.published_at)}</span>
            </a>
          ))}
        </div>
      )}
    </Panel>
  );
}

export function SentimentDot({ sentiment }: { sentiment?: string | null }) {
  const color =
    sentiment === "positive" ? "bg-up" : sentiment === "negative" ? "bg-down" : "bg-faint";
  return <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${color}`} />;
}

function numOrNull(v: string | null | undefined): number | null {
  return v === null || v === undefined ? null : parseFloat(v);
}
function scaled(v: number | null): number | null {
  return v === null ? null : Math.round(v * 1000) / 10;
}
