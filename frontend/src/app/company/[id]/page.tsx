"use client";
import { AnimatePresence, motion } from "framer-motion";
import { use, useEffect, useState } from "react";

import { CompanyHeader } from "@/components/company/header";
import { AiTab } from "@/components/company/tab-ai";
import { FinancialsTab } from "@/components/company/tab-financials";
import { NewsTab } from "@/components/company/tab-news";
import { OverviewTab } from "@/components/company/tab-overview";
import { QuantTab } from "@/components/company/tab-quant";
import { RatiosTab } from "@/components/company/tab-ratios";
import { ValuationTab } from "@/components/company/tab-valuation";
import { Skeleton } from "@/components/ui/primitives";
import { useCompany } from "@/hooks/use-api";
import { useWorkspace } from "@/lib/store";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "financials", label: "Financials" },
  { key: "valuation", label: "Valuation" },
  { key: "ratios", label: "Ratios" },
  { key: "quant", label: "Quant" },
  { key: "news", label: "News" },
  { key: "ai", label: "AI Insights" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export default function CompanyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [tab, setTab] = useState<TabKey>("overview");
  const { data, isLoading, error } = useCompany(id);
  const pushRecent = useWorkspace((s) => s.pushRecent);

  const company = data?.data;

  useEffect(() => {
    if (company) {
      const listing = company.listings.find((l) => l.is_primary) ?? company.listings[0];
      pushRecent({
        id: company.id, name: company.name,
        ticker: listing?.ticker ?? "", exchange: listing?.exchange ?? "",
        currency: listing?.currency,
      });
    }
  }, [company, pushRecent]);

  // keyboard tab switching: 1..7
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || e.metaKey || e.ctrlKey) return;
      const idx = parseInt(e.key, 10) - 1;
      if (idx >= 0 && idx < TABS.length) setTab(TABS[idx].key);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-24 text-center">
        <div className="text-sm font-medium">Company not found</div>
        <div className="mt-1 text-xs text-muted">{String(error)}</div>
      </div>
    );
  }

  if (isLoading || !company) {
    return (
      <div className="mx-auto max-w-7xl space-y-4 px-4 py-8">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-[420px] w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-24">
      <CompanyHeader company={company} />

      {/* tab bar — sticky under navbar, animated underline */}
      <div className="no-print sticky top-12 z-40 -mx-4 border-b border-line bg-bg/85 px-4 backdrop-blur-xl">
        <div className="flex gap-1 overflow-x-auto">
          {TABS.map((t, i) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "relative whitespace-nowrap px-3 py-2.5 text-xs font-medium transition-colors",
                tab === t.key ? "text-fg" : "text-muted hover:text-fg",
              )}
            >
              {t.label}
              <span className="ml-1.5 hidden font-mono text-[9px] text-faint lg:inline">{i + 1}</span>
              {tab === t.key && (
                <motion.span
                  layoutId="tab-underline"
                  className="absolute inset-x-2 -bottom-px h-[2px] rounded-full bg-accent"
                  transition={{ type: "spring", stiffness: 420, damping: 36 }}
                />
              )}
            </button>
          ))}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.18 }}
          className="pt-5"
        >
          {tab === "overview" && <OverviewTab id={id} company={company} />}
          {tab === "financials" && <FinancialsTab id={id} />}
          {tab === "valuation" && <ValuationTab id={id} />}
          {tab === "ratios" && <RatiosTab id={id} />}
          {tab === "quant" && <QuantTab id={id} />}
          {tab === "news" && <NewsTab id={id} />}
          {tab === "ai" && <AiTab id={id} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
