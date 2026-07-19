"use client";
/** News desk: sentiment timeline, classified article stream with importance
 *  badges, live refresh through the provider chain. */
import { ArrowPathIcon, ArrowUpRightIcon } from "@heroicons/react/24/outline";
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { SentimentDot } from "@/components/company/tab-overview";
import { Badge, Button, EmptyState, Panel, PanelHeader, Reveal, Skeleton } from "@/components/ui/primitives";
import { useNews, useRefreshNews, useSentimentTimeline } from "@/hooks/use-api";
import { relTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export function NewsTab({ id }: { id: string }) {
  const { data, isLoading } = useNews(id);
  const refresh = useRefreshNews(id);
  const articles = data?.data.articles ?? [];

  return (
    <div className="space-y-4">
      <Reveal><TimelinePanel id={id} /></Reveal>

      <Reveal delay={0.06}>
        <Panel>
          <PanelHeader
            title={`Article stream ${articles.length ? `(${articles.length})` : ""}`}
            right={
              <Button variant="ghost" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
                <ArrowPathIcon className={cn("h-3 w-3", refresh.isPending && "animate-spin")} />
                {refresh.isPending ? "Fetching & classifying…" : "Refresh news"}
              </Button>
            }
          />
          {isLoading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
            </div>
          ) : articles.length === 0 ? (
            <EmptyState
              title="No articles ingested"
              detail="Pulls from NewsAPI, GDELT and Yahoo, dedupes across outlets, then classifies sentiment and materiality."
              action={
                <Button variant="primary" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
                  {refresh.isPending ? "Working…" : "Fetch news"}
                </Button>
              }
            />
          ) : (
            <div className="divide-y divide-line">
              {articles.map((a) => (
                <a
                  key={a.id}
                  href={a.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-surface-2"
                >
                  <div className="mt-1.5"><SentimentDot sentiment={a.analysis?.sentiment} /></div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-3">
                      <span className="text-[13px] leading-snug">{a.headline}</span>
                      <ArrowUpRightIcon className="mt-0.5 h-3 w-3 shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-faint">
                      <span>{a.outlet ?? a.provider}</span>
                      <span>·</span>
                      <span>{relTime(a.published_at)}</span>
                      {a.analysis && (
                        <>
                          {a.analysis.category && a.analysis.category !== "unclassified" && (
                            <Badge tone="neutral" className="uppercase">{a.analysis.category}</Badge>
                          )}
                          {a.analysis.importance >= 0.7 && (
                            <Badge tone="warn">HIGH IMPACT</Badge>
                          )}
                          <Badge tone={a.analysis.sentiment === "positive" ? "up"
                            : a.analysis.sentiment === "negative" ? "down" : "neutral"}>
                            {a.analysis.sentiment} {a.analysis.sentiment_score > 0 ? "+" : ""}
                            {a.analysis.sentiment_score.toFixed(1)}
                          </Badge>
                        </>
                      )}
                    </div>
                    {a.analysis?.expected_impact &&
                      a.analysis.method.startsWith("llm") && (
                      <p className="mt-1.5 max-w-2xl text-[11px] leading-relaxed text-muted">
                        {a.analysis.expected_impact}
                      </p>
                    )}
                  </div>
                </a>
              ))}
            </div>
          )}
        </Panel>
      </Reveal>
    </div>
  );
}

function TimelinePanel({ id }: { id: string }) {
  const { data, isLoading } = useSentimentTimeline(id);
  const rows = data?.data.timeline ?? [];
  return (
    <Panel>
      <PanelHeader title="Sentiment timeline — 90 days" />
      <div className="h-[160px] p-2">
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : rows.length === 0 ? (
          <EmptyState title="No classified articles yet" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="sentiment-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--up)" stopOpacity={0.3} />
                  <stop offset="50%" stopColor="var(--up)" stopOpacity={0.02} />
                  <stop offset="100%" stopColor="var(--down)" stopOpacity={0.2} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     minTickGap={60} tickLine={false} axisLine={false} />
              <YAxis domain={[-1, 1]} orientation="right"
                     tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                     tickLine={false} axisLine={false} width={34} />
              <ReferenceLine y={0} stroke="var(--border-strong)" />
              <Tooltip
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-2.5 py-1.5 text-xs shadow-xl">
                      <div className="text-faint">{label as string}</div>
                      <div className="tnum mt-0.5 font-mono">
                        avg {(payload[0].value as number).toFixed(2)} ·{" "}
                        {(payload[0].payload as { count: number }).count} articles
                      </div>
                    </div>
                  ) : null}
              />
              <Area type="monotone" dataKey="avg_sentiment" stroke="var(--accent)"
                    strokeWidth={1.5} fill="url(#sentiment-fill)" animationDuration={700} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Panel>
  );
}
