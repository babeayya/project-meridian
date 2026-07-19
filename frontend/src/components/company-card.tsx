"use client";
/** Mouse-reactive company card with live quote + sparkline (real prices). */
import { useQuery } from "@tanstack/react-query";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import Link from "next/link";
import { useRef } from "react";

import { get, type PriceSeries, type Quote } from "@/lib/api";
import { deltaClass, pct, price } from "@/lib/format";
import type { TrackedCompany } from "@/lib/store";
import { cn } from "@/lib/utils";

export function CompanyCard({ company }: { company: TrackedCompany }) {
  const ref = useRef<HTMLDivElement>(null);
  const mx = useMotionValue(0.5);
  const my = useMotionValue(0.5);
  const rotateX = useSpring(useTransform(my, [0, 1], [3.5, -3.5]), { stiffness: 200, damping: 24 });
  const rotateY = useSpring(useTransform(mx, [0, 1], [-3.5, 3.5]), { stiffness: 200, damping: 24 });

  const { data: quote } = useQuery({
    queryKey: ["quote", company.id],
    queryFn: () => get<Quote>(`/companies/${company.id}/quote`),
    staleTime: 30_000,
  });
  const { data: prices } = useQuery({
    queryKey: ["prices", company.id, "3m"],
    queryFn: () => get<PriceSeries>(`/companies/${company.id}/prices?range=3m`),
    staleTime: 5 * 60_000,
  });

  const q = quote?.data;
  const points = prices?.data.points ?? [];

  return (
    <motion.div
      ref={ref}
      style={{ rotateX, rotateY, transformPerspective: 900 }}
      onMouseMove={(e) => {
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        mx.set((e.clientX - r.left) / r.width);
        my.set((e.clientY - r.top) / r.height);
      }}
      onMouseLeave={() => { mx.set(0.5); my.set(0.5); }}
    >
      <Link
        href={`/company/${company.id}`}
        className="panel panel-hover block p-4"
      >
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-sm font-semibold">{company.ticker}</span>
              <span className="text-[10px] text-faint">{company.exchange}</span>
            </div>
            <div className="mt-0.5 max-w-[180px] truncate text-xs text-muted">{company.name}</div>
          </div>
          {q && (
            <div className="text-right">
              <div className="tnum font-mono text-sm font-medium">
                {price(q.price, q.currency)}
              </div>
              <div className={cn("tnum font-mono text-[11px]", deltaClass(q.change_pct))}>
                {pct(q.change_pct, { signed: true, scaled: true })}
              </div>
            </div>
          )}
        </div>
        <div className="mt-3">
          <Sparkline points={points.map((p) => parseFloat(p.close))} />
        </div>
      </Link>
    </motion.div>
  );
}

function Sparkline({ points }: { points: number[] }) {
  if (points.length < 2) return <div className="h-9" />;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 220, h = 36;
  const d = points
    .map((v, i) =>
      `${i === 0 ? "M" : "L"}${((i / (points.length - 1)) * w).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`)
    .join(" ");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-9 w-full" preserveAspectRatio="none">
      <path
        d={d}
        fill="none"
        stroke={up ? "var(--up)" : "var(--down)"}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
