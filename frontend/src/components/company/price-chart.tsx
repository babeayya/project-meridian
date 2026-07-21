"use client";
/** Interactive price chart: range switcher, crosshair tooltip, brush zoom,
 *  fullscreen. Recharts over real OHLCV. */
import { ArrowsPointingOutIcon, ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { useMemo, useRef, useState } from "react";
import {
  Area, AreaChart, Brush, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import { Panel, PanelHeader, Skeleton } from "@/components/ui/primitives";
import { usePrices } from "@/hooks/use-api";
import { price as fmtPrice } from "@/lib/format";
import { cn, downloadCsv } from "@/lib/utils";

const RANGES = ["1m", "3m", "6m", "1y", "2y", "5y"] as const;
type Range = (typeof RANGES)[number];

/** Axis granularity has to track the window: a month of bars labelled by
 *  month+year just repeats "Jun 26". Short ranges get day-first dates
 *  ("26 Jun") so they never read as an ambiguous month-year. */
const AXIS_FORMAT: Record<Range, Intl.DateTimeFormatOptions> = {
  "1m": { day: "numeric", month: "short" },
  "3m": { day: "numeric", month: "short" },
  "6m": { day: "numeric", month: "short" },
  "1y": { month: "short", year: "2-digit" },
  "2y": { month: "short", year: "2-digit" },
  "5y": { month: "short", year: "2-digit" },
};
const AXIS_LOCALE: Record<Range, string> = {
  "1m": "en-GB", "3m": "en-GB", "6m": "en-GB",
  "1y": "en-US", "2y": "en-US", "5y": "en-US",
};

export function PriceChart({ id, currency }: { id: string; currency?: string | null }) {
  const [range, setRange] = useState<Range>("1y");
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { data, isLoading } = usePrices(id, range);

  const points = useMemo(
    () =>
      (data?.data.points ?? []).map((p) => ({
        date: p.date,
        close: parseFloat(p.close),
        volume: p.volume,
      })),
    [data],
  );

  const up = points.length >= 2 && points[points.length - 1].close >= points[0].close;
  const color = up ? "var(--up)" : "var(--down)";

  const exportCsv = () =>
    downloadCsv(`${data?.data.ticker ?? "prices"}-${range}.csv`, [
      ["date", "close", "volume"],
      ...points.map((p) => [p.date, p.close, p.volume]),
    ]);

  return (
    <Panel
      className={cn(fullscreen &&
        "fixed inset-4 z-[80] flex flex-col shadow-2xl")}
    >
      <PanelHeader
        title={
          <span className="flex items-center gap-2">
            Price
            {data && (
              <span className="normal-case tracking-normal text-faint">
                {data.data.ticker} · {data.meta.sources.join(", ")}
              </span>
            )}
          </span>
        }
        right={
          <div className="no-print flex items-center gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={cn(
                  "rounded px-2 py-0.5 font-mono text-[11px] transition-colors",
                  range === r ? "bg-accent/15 text-accent" : "text-muted hover:text-fg",
                )}
              >
                {r.toUpperCase()}
              </button>
            ))}
            <span className="mx-1 h-4 w-px bg-line" />
            <button onClick={exportCsv} className="p-1 text-muted hover:text-fg" title="Download CSV">
              <ArrowDownTrayIcon className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => setFullscreen((v) => !v)}
              className="p-1 text-muted hover:text-fg"
              title="Fullscreen"
            >
              <ArrowsPointingOutIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        }
      />
      <div ref={containerRef} className={cn("p-2", fullscreen ? "min-h-0 flex-1" : "h-[320px]")}>
        {isLoading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={`fill-${id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.22} />
                  <stop offset="100%" stopColor={color} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--grid-line)" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "var(--text-faint)" }}
                tickLine={false} axisLine={false}
                minTickGap={60}
                tickFormatter={(d: string) =>
                  new Date(d).toLocaleDateString(AXIS_LOCALE[range], AXIS_FORMAT[range])}
              />
              <YAxis
                orientation="right"
                domain={["auto", "auto"]}
                tick={{ fontSize: 10, fill: "var(--text-faint)", fontFamily: "var(--font-jbmono)" }}
                tickLine={false} axisLine={false} width={56}
                tickFormatter={(v: number) => v.toFixed(0)}
              />
              <Tooltip
                cursor={{ stroke: "var(--border-strong)", strokeDasharray: "3 3" }}
                content={({ active, payload, label }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-line bg-surface px-3 py-2 text-xs shadow-xl">
                      <div className="text-faint">
                        {new Date(label as string).toLocaleDateString("en-US", {
                          day: "numeric", month: "short", year: "numeric",
                        })}
                      </div>
                      <div className="tnum mt-0.5 font-mono font-semibold">
                        {fmtPrice(payload[0].value as number, currency)}
                      </div>
                    </div>
                  ) : null
                }
              />
              <Area
                type="monotone"
                dataKey="close"
                stroke={color}
                strokeWidth={1.6}
                fill={`url(#fill-${id})`}
                animationDuration={600}
              />
              {points.length > 40 && (
                <Brush
                  dataKey="date"
                  height={22}
                  stroke="var(--border-strong)"
                  fill="var(--surface-2)"
                  travellerWidth={7}
                  tickFormatter={() => ""}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
      {fullscreen && (
        <button
          onClick={() => setFullscreen(false)}
          className="absolute right-3 top-3 rounded-md border border-line bg-surface-2 px-2 py-1 text-[11px] text-muted"
        >
          ESC to close
        </button>
      )}
    </Panel>
  );
}
