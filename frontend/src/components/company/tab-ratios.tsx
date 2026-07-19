"use client";
/** Ratio engine + DuPont + forensic scores. Every ratio opens its full
 *  calculation trace — the interactive formula explorer. */
import { XMarkIcon } from "@heroicons/react/24/outline";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { TraceView } from "@/components/company/trace-view";
import { Badge, EmptyState, Panel, PanelHeader, Reveal, Skeleton } from "@/components/ui/primitives";
import { useDupont, useRatios, useScores } from "@/hooks/use-api";
import type { CalcNode, ScoreResult } from "@/lib/api";
import { byUnit } from "@/lib/format";
import { cn } from "@/lib/utils";

const GROUP_LABELS: Record<string, string> = {
  profitability: "Profitability",
  liquidity: "Liquidity",
  leverage: "Leverage & Coverage",
  efficiency: "Efficiency",
  market: "Market Multiples",
};

export function RatiosTab({ id }: { id: string }) {
  const { data, isLoading, error } = useRatios(id);
  const [selected, setSelected] = useState<CalcNode | null>(null);

  if (error) {
    return (
      <Panel>
        <EmptyState title="Ratios unavailable"
                    detail="Ingest fundamentals first (header → Refresh data)." />
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : (
        Object.entries(data!.data.groups).map(([group, ratios], gi) => (
          <Reveal key={group} delay={gi * 0.05}>
            <div className="label mb-2">{GROUP_LABELS[group] ?? group}</div>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {Object.entries(ratios).map(([key, node]) => (
                <button
                  key={key}
                  onClick={() => setSelected(node)}
                  className="panel panel-hover p-3 text-left"
                  title="Click for the full calculation trace"
                >
                  <div className="truncate text-[11px] text-muted">{node.label}</div>
                  <div className="tnum mt-1 font-mono text-lg font-semibold">
                    {byUnit(node.result, node.unit, data!.data.currency)}
                  </div>
                  <div className="mt-1 truncate font-mono text-[9px] text-faint">
                    {node.formula}
                  </div>
                </button>
              ))}
            </div>
          </Reveal>
        ))
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Reveal delay={0.1}><DupontPanel id={id} onOpenTrace={setSelected} /></Reveal>
        <Reveal delay={0.14}><ScoresPanel id={id} /></Reveal>
      </div>

      {/* trace drawer */}
      <AnimatePresence>
        {selected && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 backdrop-blur-sm sm:items-center"
            onClick={() => setSelected(null)}
          >
            <motion.div
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 30, opacity: 0 }}
              transition={{ type: "spring", stiffness: 380, damping: 34 }}
              onClick={(e) => e.stopPropagation()}
              className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-t-xl border border-line-strong bg-surface p-4 shadow-2xl sm:rounded-xl"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="label">Calculation trace</span>
                <button onClick={() => setSelected(null)} className="text-muted hover:text-fg">
                  <XMarkIcon className="h-4 w-4" />
                </button>
              </div>
              <TraceView node={selected} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function DupontPanel({ id, onOpenTrace }: {
  id: string; onOpenTrace: (n: CalcNode) => void;
}) {
  const { data, isLoading, error } = useDupont(id);
  const node = data?.data;
  return (
    <Panel>
      <PanelHeader title="DuPont decomposition" />
      {isLoading ? <Skeleton className="m-4 h-24" /> : error || !node ? (
        <EmptyState title="Insufficient data for DuPont" />
      ) : (
        <div className="p-4">
          <div className="flex flex-wrap items-center gap-2">
            {node.inputs.map((inp, i) => (
              <div key={inp.name} className="flex items-center gap-2">
                <div className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-center">
                  <div className="text-[9px] uppercase tracking-wide text-faint">{inp.symbol}</div>
                  <div className="tnum mt-0.5 font-mono text-sm font-semibold">
                    {byUnit(inp.value, inp.unit)}
                  </div>
                </div>
                {i < node.inputs.length - 1 && <span className="text-faint">×</span>}
              </div>
            ))}
            <span className="text-faint">=</span>
            <div className="rounded-lg border border-accent/30 bg-accent/10 px-3 py-2 text-center">
              <div className="text-[9px] uppercase tracking-wide text-accent">ROE</div>
              <div className="tnum mt-0.5 font-mono text-sm font-semibold text-accent">
                {byUnit(node.result, node.unit)}
              </div>
            </div>
          </div>
          <button
            onClick={() => onOpenTrace(node)}
            className="mt-3 text-[11px] text-accent hover:underline"
          >
            Open full trace →
          </button>
        </div>
      )}
    </Panel>
  );
}

function ScoresPanel({ id }: { id: string }) {
  const { data, isLoading, error } = useScores(id);
  if (isLoading) return <Panel><Skeleton className="m-4 h-32" /></Panel>;
  if (error || !data) return <Panel><EmptyState title="Scores unavailable" /></Panel>;
  const { altman_z, piotroski_f, beneish_m } = data.data.classic;
  return (
    <Panel>
      <PanelHeader
        title="Forensic scores"
        right={<Badge tone="accent">composite {data.data.composite.score}/100</Badge>}
      />
      <div className="grid grid-cols-3 divide-x divide-line">
        <ScoreCell label="Altman Z" score={altman_z}
                   toneFor={(g) => g === "safe" ? "up" : g === "grey" ? "warn" : "down"} />
        <ScoreCell label="Piotroski F" score={piotroski_f} suffix="/9"
                   toneFor={(g) => g === "strong" ? "up" : g === "moderate" ? "warn" : "down"} />
        <ScoreCell label="Beneish M" score={beneish_m}
                   toneFor={(g) => g === "clean" ? "up" : "down"} />
      </div>
      <div className="border-t border-line px-4 py-3">
        <div className="flex flex-wrap gap-3">
          {Object.values(data.data.factors).map((f) => (
            <div key={f.pillar} className="flex items-center gap-1.5" title={`coverage ${Math.round(f.coverage * 100)}%`}>
              <span className="text-[10px] capitalize text-muted">{f.pillar}</span>
              <span className={cn("tnum font-mono text-[11px] font-semibold",
                f.score >= 60 ? "text-up" : f.score >= 35 ? "text-warn" : "text-down")}>
                {f.score}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function ScoreCell({ label, score, suffix = "", toneFor }: {
  label: string; score: ScoreResult | null; suffix?: string;
  toneFor: (grade: string) => "up" | "down" | "warn";
}) {
  return (
    <div className="px-4 py-3">
      <div className="label">{label}</div>
      {score === null ? (
        <div className="mt-1 text-xs text-faint">—</div>
      ) : score.not_applicable_reason ? (
        <div className="mt-1 text-[10px] text-faint" title={score.not_applicable_reason}>n/a</div>
      ) : (
        <>
          <div className="tnum mt-1 font-mono text-lg font-semibold">
            {parseFloat(score.value).toFixed(2).replace(/\.00$/, "")}{suffix}
          </div>
          <Badge tone={toneFor(score.grade)} className="mt-1 uppercase">{score.grade}</Badge>
        </>
      )}
    </div>
  );
}
