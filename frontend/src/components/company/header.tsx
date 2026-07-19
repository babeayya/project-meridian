"use client";
/** Company masthead: live quote (30s poll), market cap, blended intrinsic
 *  value + margin of safety from the latest valuation runs. */
import {
  ArrowPathIcon,
  ArrowUpRightIcon,
  BookmarkIcon as BookmarkOutline,
  PrinterIcon,
} from "@heroicons/react/24/outline";
import { BookmarkIcon as BookmarkSolid } from "@heroicons/react/24/solid";

import { Badge, Button, ConfidenceMeter, CountUp } from "@/components/ui/primitives";
import { useBridge, useQuote, useRefreshFundamentals } from "@/hooks/use-api";
import type { CompanyProfile } from "@/lib/api";
import { currencySymbol, deltaClass, money, pct, relTime } from "@/lib/format";
import { useWorkspace } from "@/lib/store";
import { cn } from "@/lib/utils";

export function CompanyHeader({ company }: { company: CompanyProfile }) {
  const listing = company.listings.find((l) => l.is_primary) ?? company.listings[0];
  const { data: quote } = useQuote(company.id);
  const { data: bridge } = useBridge(company.id);
  const refresh = useRefreshFundamentals(company.id);
  const { watchlist, toggleWatch } = useWorkspace();

  const q = quote?.data;
  const currency = q?.currency ?? listing?.currency ?? company.reporting_currency;
  const watched = watchlist.some((w) => w.id === company.id);

  // blended intrinsic view from stored runs (only ok models)
  const models = bridge?.data.models ?? [];
  const blended = models.length
    ? models.reduce((s, m) => s + parseFloat(m.fair_value) * m.confidence, 0) /
      models.reduce((s, m) => s + m.confidence, 0)
    : null;
  const priceNum = q ? parseFloat(q.price) : null;
  const mos = blended && priceNum ? 1 - priceNum / blended : null;
  const avgConfidence = models.length
    ? models.reduce((s, m) => s + m.confidence, 0) / models.length
    : null;

  return (
    <header className="py-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight">{company.name}</h1>
            <Badge tone="neutral">
              <span className="font-mono font-semibold">{listing?.ticker}</span>
              <span className="text-faint">·</span>
              {listing?.exchange}
            </Badge>
            {company.sector && <Badge tone="accent">{company.sector}</Badge>}
          </div>
          <div className="mt-1 text-[11px] text-muted">
            {company.country}
            {q && <> · quote {relTime(q.as_of)} via {q.source}</>}
          </div>
        </div>

        <div className="no-print flex items-center gap-2">
          <Button
            variant="ghost"
            onClick={() => toggleWatch({
              id: company.id, name: company.name,
              ticker: listing?.ticker ?? "", exchange: listing?.exchange ?? "",
              currency,
            })}
            title={watched ? "Remove from watchlist" : "Add to watchlist"}
          >
            {watched
              ? <BookmarkSolid className="h-3.5 w-3.5 text-accent" />
              : <BookmarkOutline className="h-3.5 w-3.5" />}
            {watched ? "Watching" : "Watch"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            title="Re-ingest fundamentals through the provider chain"
          >
            <ArrowPathIcon className={cn("h-3.5 w-3.5", refresh.isPending && "animate-spin")} />
            {refresh.isPending ? "Refreshing…" : "Refresh data"}
          </Button>
          <Button variant="ghost" onClick={() => window.print()} title="Export to PDF">
            <PrinterIcon className="h-3.5 w-3.5" />
          </Button>
          {company.website && (
            <a
              href={company.website}
              target="_blank"
              rel="noreferrer"
              className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-fg"
              title="Investor site"
            >
              <ArrowUpRightIcon className="h-3.5 w-3.5" />
            </a>
          )}
        </div>
      </div>

      {/* stat strip */}
      <div className="mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3 lg:grid-cols-6">
        <HeaderStat label="Last price">
          {priceNum !== null ? (
            <span className="flex items-baseline gap-2">
              <CountUp
                value={priceNum}
                format={(n) => `${currencySymbol(currency)}${n.toFixed(2)}`}
                className="font-mono text-lg font-semibold"
              />
              {q?.change_pct && (
                <span className={cn("tnum font-mono text-xs", deltaClass(q.change_pct))}>
                  {pct(q.change_pct, { signed: true, scaled: true })}
                </span>
              )}
            </span>
          ) : "—"}
        </HeaderStat>
        <HeaderStat label="Market cap">
          {q?.market_cap ? money(q.market_cap, currency)
            : blended && priceNum ? "—" : "—"}
        </HeaderStat>
        <HeaderStat label="Blended intrinsic">
          {blended !== null
            ? <span className="font-mono">{currencySymbol(currency)}{blended.toFixed(2)}</span>
            : <span className="text-xs text-faint">run valuation →</span>}
        </HeaderStat>
        <HeaderStat label="Margin of safety">
          {mos !== null ? (
            <span className={cn("font-mono", mos > 0 ? "text-up" : "text-down")}>
              {pct(mos, { signed: true })}
            </span>
          ) : "—"}
        </HeaderStat>
        <HeaderStat label="Model verdict">
          {mos === null ? "—" : (
            <Badge tone={mos > 0.15 ? "up" : mos < -0.15 ? "down" : "warn"}>
              {mos > 0.15 ? "UNDERVALUED" : mos < -0.15 ? "PREMIUM TO VALUE" : "FAIRLY VALUED"}
            </Badge>
          )}
        </HeaderStat>
        <HeaderStat label="Model confidence">
          {avgConfidence !== null ? <ConfidenceMeter value={avgConfidence} /> : "—"}
        </HeaderStat>
      </div>
    </header>
  );
}

function HeaderStat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="bg-surface px-4 py-3">
      <div className="label">{label}</div>
      <div className="tnum mt-1 text-sm">{children}</div>
    </div>
  );
}
