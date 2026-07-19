"use client";
/** Marquee ribbon of live quotes for tracked companies — real backend data,
 *  hidden entirely until the user tracks at least one company. */
import { useQueries } from "@tanstack/react-query";
import Link from "next/link";

import { get, type Quote } from "@/lib/api";
import { deltaClass, pct, price } from "@/lib/format";
import { useWorkspace } from "@/lib/store";
import { cn } from "@/lib/utils";

export function TickerTape() {
  const watchlist = useWorkspace((s) => s.watchlist);
  const results = useQueries({
    queries: watchlist.slice(0, 12).map((c) => ({
      queryKey: ["quote", c.id],
      queryFn: () => get<Quote>(`/companies/${c.id}/quote`),
      refetchInterval: 60_000,
      staleTime: 30_000,
    })),
  });

  const entries = watchlist
    .slice(0, 12)
    .map((c, i) => ({ company: c, quote: results[i]?.data?.data }))
    .filter((e) => e.quote);

  if (entries.length === 0) return null;
  const loop = [...entries, ...entries]; // seamless wrap

  return (
    <div className="no-print overflow-hidden border-b border-line bg-surface/60">
      <div className="animate-marquee flex w-max items-center gap-8 px-6 py-2">
        {loop.map(({ company, quote }, i) => (
          <Link
            key={`${company.id}-${i}`}
            href={`/company/${company.id}`}
            className="flex items-baseline gap-2 whitespace-nowrap text-xs transition-opacity hover:opacity-70"
          >
            <span className="font-mono font-semibold">{company.ticker}</span>
            <span className="tnum font-mono">{price(quote!.price, quote!.currency)}</span>
            <span className={cn("tnum font-mono text-[11px]", deltaClass(quote!.change_pct))}>
              {pct(quote!.change_pct, { signed: true, scaled: true })}
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
