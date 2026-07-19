"use client";
/** Landing / markets home. Everything rendered is real: live resolve search,
 *  quotes for tracked companies, provider health. No fabricated indices. */
import {
  ArrowTrendingUpIcon,
  BeakerIcon,
  CircleStackIcon,
  CpuChipIcon,
  DocumentMagnifyingGlassIcon,
  ScaleIcon,
} from "@heroicons/react/24/outline";
import { motion, useScroll, useTransform } from "framer-motion";
import { useRef } from "react";

import { CompanyCard } from "@/components/company-card";
import { SearchHero } from "@/components/search-hero";
import { TickerTape } from "@/components/ticker-tape";
import { CountUp, Panel, Reveal } from "@/components/ui/primitives";
import { useProviderHealth } from "@/hooks/use-api";
import { useWorkspace } from "@/lib/store";

export default function Home() {
  const { watchlist, recent } = useWorkspace();
  const { data: health } = useProviderHealth();
  const heroRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const gridY = useTransform(scrollYProgress, [0, 1], [0, 80]);
  const fade = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  return (
    <div>
      <TickerTape />

      {/* ── hero ────────────────────────────────────────────────────────── */}
      <section ref={heroRef} className="relative overflow-hidden">
        <motion.div
          style={{ y: gridY }}
          className="bg-grid bg-grid-fade pointer-events-none absolute inset-0"
        />
        <motion.div style={{ opacity: fade }} className="relative mx-auto max-w-7xl px-4 pb-24 pt-24 sm:pt-32">
          <Reveal className="mx-auto max-w-3xl text-center">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[11px] text-muted">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-up" />
              Multi-source ingestion · SEC EDGAR · Yahoo · NewsAPI · GDELT
            </div>
            <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
              Institutional research on{" "}
              <span className="text-accent">any listed company</span>
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-pretty text-sm leading-relaxed text-muted">
              Auditable valuations, ten years of fundamentals, quant analytics and
              AI analysis — every number traceable to its formula, inputs and source.
            </p>
          </Reveal>

          <Reveal delay={0.12} className="mt-9">
            <SearchHero />
          </Reveal>

          <Reveal delay={0.22}>
            <div className="mx-auto mt-14 grid max-w-2xl grid-cols-3 gap-px overflow-hidden rounded-xl border border-line bg-line">
              <HeroStat value={11} suffix="" label="Valuation models" />
              <HeroStat value={60} suffix="+" label="Ratios & scores" />
              <HeroStat value={health?.providers.length ?? 0} suffix="" label="Live data feeds" />
            </div>
          </Reveal>
        </motion.div>
      </section>

      {/* ── workspace ───────────────────────────────────────────────────── */}
      {(watchlist.length > 0 || recent.length > 0) && (
        <section className="mx-auto max-w-7xl px-4 pb-10">
          {watchlist.length > 0 && (
            <Reveal>
              <div className="label">Watchlist</div>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {watchlist.map((c) => <CompanyCard key={c.id} company={c} />)}
              </div>
            </Reveal>
          )}
          {recent.length > 0 && (
            <Reveal delay={0.08}>
              <div className="label mt-10">Recently viewed</div>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {recent.slice(0, 4).map((c) => <CompanyCard key={c.id} company={c} />)}
              </div>
            </Reveal>
          )}
        </section>
      )}

      {/* ── capabilities ────────────────────────────────────────────────── */}
      <section className="border-t border-line bg-surface/40">
        <div className="mx-auto max-w-7xl px-4 py-20">
          <Reveal>
            <div className="label">The research stack</div>
            <h2 className="mt-2 max-w-lg text-2xl font-semibold tracking-tight">
              Every number reproducible. Every source cited.
            </h2>
          </Reveal>
          <div className="mt-10 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 0.06}>
                <Panel hover className="h-full p-5">
                  <f.icon className="h-5 w-5 text-accent" />
                  <h3 className="mt-3 text-sm font-semibold">{f.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{f.body}</p>
                </Panel>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-6 text-[11px] text-faint">
          <span>Meridian Equity Research — analysis engine output, not investment advice.</span>
          <span className="font-mono">v0.2</span>
        </div>
      </footer>
    </div>
  );
}

function HeroStat({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  return (
    <div className="bg-surface px-6 py-5 text-center">
      <div className="font-mono text-2xl font-semibold">
        <CountUp value={value} format={(n) => `${Math.round(n)}${suffix}`} duration={1.2} />
      </div>
      <div className="label mt-1">{label}</div>
    </div>
  );
}

const FEATURES = [
  {
    icon: ScaleIcon,
    title: "Auditable valuation engine",
    body: "DCF, residual income, EVA, DDM, Monte Carlo and more — each result ships its formula, substituted values, intermediates and confidence.",
  },
  {
    icon: CircleStackIcon,
    title: "Multi-source fundamentals",
    body: "SEC EDGAR XBRL as the authoritative US source with Yahoo and FMP fallback chains; balance-sheet validation gates on every payload.",
  },
  {
    icon: ArrowTrendingUpIcon,
    title: "Quant analytics",
    body: "CAPM beta, Sharpe, Sortino, VaR and expected shortfall, rolling factor exposure — computed from real return series.",
  },
  {
    icon: BeakerIcon,
    title: "DCF playground",
    body: "Edit growth, margins, WACC and terminal assumptions; the model re-prices instantly with the full trace attached.",
  },
  {
    icon: DocumentMagnifyingGlassIcon,
    title: "Forensic scoring",
    body: "Altman Z, Piotroski F, Beneish M-Score and factor pillars with the underlying arithmetic exposed for every component.",
  },
  {
    icon: CpuChipIcon,
    title: "AI analyst desk",
    body: "Seven specialist agents and a thesis synthesizer that interpret the engine's numbers — they never invent their own.",
  },
];
