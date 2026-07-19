"use client";
/** AI analyst desk: stored agent outputs (thesis, moat, risks, red flags…)
 *  rendered as structured research; agents run on demand via the backend. */
import {
  ArrowPathIcon, CheckCircleIcon, CpuChipIcon, ExclamationTriangleIcon, PlayIcon,
} from "@heroicons/react/24/outline";
import { useState } from "react";

import { Badge, Button, ConfidenceMeter, EmptyState, Panel, PanelHeader, Reveal, Skeleton } from "@/components/ui/primitives";
import { useAiAnalyses, useRunAgent } from "@/hooks/use-api";
import type { AiAnalysis } from "@/lib/api";
import { relTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const AGENT_LABELS: Record<string, string> = {
  thesis: "Investment Thesis",
  financial_statement: "Financial Statements",
  valuation: "Valuation Review",
  moat: "Economic Moat",
  risk: "Risk Register",
  red_flag: "Accounting Red Flags",
  news: "News Synthesis",
};
// Independent agents first; thesis LAST because it reads the others' outputs.
const RUN_ORDER = ["financial_statement", "news", "moat", "valuation",
                   "risk", "red_flag", "thesis"];

interface Progress {
  current: string | null;
  done: string[];
  failed: Record<string, string>;
}

export function AiTab({ id }: { id: string }) {
  const { data, isLoading } = useAiAnalyses(id);
  const run = useRunAgent(id);
  const [progress, setProgress] = useState<Progress | null>(null);

  const running = progress !== null && progress.current !== null;

  const analyses = (data?.data.analyses ?? [])
    .slice()
    .sort((a, b) => RUN_ORDER.indexOf(a.agent) - RUN_ORDER.indexOf(b.agent));

  // Drive agents ONE AT A TIME. Each request is short (~2–3 min on free models),
  // results stream in after every agent, and a single failure never aborts the rest.
  const runAll = async () => {
    const available = data?.data.available_agents ?? [];
    const order = RUN_ORDER.filter((a) => available.includes(a));
    setProgress({ current: null, done: [], failed: {} });
    for (const agent of order) {
      setProgress((p) => ({ ...(p as Progress), current: agent }));
      try {
        const res = await run.mutateAsync(agent);
        const err = res.data.errors[agent];
        setProgress((p) => ({
          current: null,
          done: [...(p as Progress).done, agent],
          failed: err ? { ...(p as Progress).failed, [agent]: err } : (p as Progress).failed,
        }));
      } catch (e) {
        setProgress((p) => ({
          current: null,
          done: [...(p as Progress).done, agent],
          failed: { ...(p as Progress).failed, [agent]: String(e) },
        }));
      }
    }
  };

  const runOne = async (agent: string) => {
    setProgress({ current: agent, done: [], failed: {} });
    try {
      const res = await run.mutateAsync(agent);
      const err = res.data.errors[agent];
      setProgress({ current: null, done: [agent], failed: err ? { [agent]: err } : {} });
    } catch (e) {
      setProgress({ current: null, done: [agent], failed: { [agent]: String(e) } });
    }
  };

  const order = (data?.data.available_agents ?? [])
    .slice()
    .sort((a, b) => RUN_ORDER.indexOf(a) - RUN_ORDER.indexOf(b));
  const failedEntries = Object.entries(progress?.failed ?? {});

  return (
    <div className="space-y-4">
      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div className="flex items-center gap-3">
            <CpuChipIcon className="h-5 w-5 text-accent" />
            <div>
              <div className="text-sm font-medium">AI analyst desk</div>
              <div className="text-[11px] text-muted">
                Specialist agents interpret the engine&apos;s numbers — they never compute
                figures themselves. Run sequentially · ~2–3 min each on free models.
              </div>
            </div>
          </div>
          <Button variant="primary" onClick={runAll} disabled={running}>
            <PlayIcon className="h-3.5 w-3.5" />
            {running ? "Running…" : analyses.length ? "Re-run all agents" : "Run full analysis"}
          </Button>
        </div>

        {/* live per-agent progress tracker */}
        {progress && (
          <div className="border-t border-line px-4 py-3">
            <div className="flex flex-wrap gap-1.5">
              {order.map((agent) => {
                const isDone = progress.done.includes(agent);
                const isFailed = agent in progress.failed;
                const isCurrent = progress.current === agent;
                return (
                  <span
                    key={agent}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium",
                      isCurrent && "border-accent/40 bg-accent/10 text-accent",
                      isDone && !isFailed && "border-up/20 bg-up/10 text-up",
                      isFailed && "border-down/20 bg-down/10 text-down",
                      !isDone && !isCurrent && "border-line bg-surface-2 text-faint",
                    )}
                  >
                    {isCurrent && <ArrowPathIcon className="h-3 w-3 animate-spin" />}
                    {isDone && !isFailed && <CheckCircleIcon className="h-3 w-3" />}
                    {isFailed && <ExclamationTriangleIcon className="h-3 w-3" />}
                    {AGENT_LABELS[agent] ?? agent}
                  </span>
                );
              })}
            </div>
            {running && (
              <div className="mt-2 text-[10px] text-muted">
                {progress.done.length}/{order.length} complete · the current agent may take
                a couple of minutes — results appear as each finishes.
              </div>
            )}
            {failedEntries.length > 0 && !running && (
              <div className="mt-2 space-y-1">
                {failedEntries.map(([agent, err]) => (
                  <div key={agent} className="flex items-start gap-2 text-[10px] text-warn">
                    <span className="shrink-0 font-medium">{AGENT_LABELS[agent] ?? agent}:</span>
                    <span className="min-w-0 flex-1">{err}</span>
                    <button
                      onClick={() => runOne(agent)}
                      className="shrink-0 text-accent hover:underline"
                    >
                      retry
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Panel>

      {isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}
        </div>
      ) : analyses.length === 0 ? (
        <Panel>
          <EmptyState
            title="No analyses yet"
            detail="Run the agent suite to generate the thesis, moat assessment, risk register and accounting review."
          />
        </Panel>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {analyses.map((a, i) => (
            <Reveal key={a.agent} delay={i * 0.05}
                    className={cn(a.agent === "thesis" && "lg:col-span-2")}>
              <AgentCard analysis={a} />
            </Reveal>
          ))}
        </div>
      )}
    </div>
  );
}

function AgentCard({ analysis }: { analysis: AiAnalysis }) {
  const o = analysis.output;
  return (
    <Panel className="h-full">
      <PanelHeader
        title={AGENT_LABELS[analysis.agent] ?? analysis.agent}
        right={
          <div className="flex items-center gap-2">
            {analysis.confidence !== null && <ConfidenceMeter value={analysis.confidence} />}
            <span className="font-mono text-[9px] text-faint" title={analysis.model}>
              {relTime(analysis.created_at)}
            </span>
          </div>
        }
      />
      <div className="space-y-3 p-4 text-xs leading-relaxed">
        {analysis.agent === "thesis" && <ThesisBody o={o} />}
        {analysis.agent === "moat" && <MoatBody o={o} />}
        {analysis.agent === "risk" && <RiskBody o={o} />}
        {analysis.agent === "red_flag" && <RedFlagBody o={o} />}
        {["financial_statement", "valuation", "news"].includes(analysis.agent) && (
          <GenericBody o={o} />
        )}
      </div>
    </Panel>
  );
}

/* narrow helpers over the loosely-typed agent JSON */
const s = (v: unknown): string => (typeof v === "string" ? v : "");
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);

function ThesisBody({ o }: { o: Record<string, unknown> }) {
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent" className="uppercase">{s(o.recommendation_stance).split(":")[0] || "view"}</Badge>
        {typeof o.business_quality_score === "number" && (
          <Badge tone="neutral">quality {o.business_quality_score}/100</Badge>
        )}
      </div>
      <p className="text-muted">{s(o.investment_thesis)}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <BulletBlock title="Bull case" tone="text-up" items={arr(o.bull_case).map(s)} />
        <BulletBlock title="Bear case" tone="text-down" items={arr(o.bear_case).map(s)} />
      </div>
      <BulletBlock title="Catalysts" tone="text-accent" items={arr(o.catalysts).map(s)} />
      {s(o.data_coverage_caveat) && (
        <p className="border-t border-line pt-2 text-[10px] text-faint">
          Coverage caveat: {s(o.data_coverage_caveat)}
        </p>
      )}
    </>
  );
}

function MoatBody({ o }: { o: Record<string, unknown> }) {
  const rating = s(o.moat_rating);
  return (
    <>
      <Badge tone={rating === "wide" ? "up" : rating === "narrow" ? "warn" : "neutral"}
             className="uppercase">
        {rating || "unrated"} moat
      </Badge>
      <ul className="space-y-2">
        {arr(o.sources).map((src, i) => {
          const m = src as Record<string, unknown>;
          return (
            <li key={i} className="rounded-md border border-line bg-surface-2 p-2.5">
              <div className="flex items-center gap-2">
                <span className="font-medium capitalize">{s(m.type).replaceAll("_", " ")}</span>
                <span className="text-[10px] text-faint">{s(m.durability)}</span>
              </div>
              <p className="mt-1 text-muted">{s(m.evidence)}</p>
            </li>
          );
        })}
      </ul>
    </>
  );
}

function RiskBody({ o }: { o: Record<string, unknown> }) {
  const risks = arr(o.risks) as Record<string, unknown>[];
  return (
    <div className="space-y-1.5">
      {risks.slice(0, 8).map((r, i) => {
        const sev = ((r.likelihood as number) ?? 0) * ((r.impact as number) ?? 0);
        return (
          <div key={i} className="flex items-center gap-2">
            <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full",
              sev >= 15 ? "bg-down" : sev >= 8 ? "bg-warn" : "bg-faint")} />
            <span className="min-w-0 flex-1 truncate" title={s(r.mitigants)}>{s(r.name)}</span>
            <span className="tnum shrink-0 font-mono text-[10px] text-faint">
              L{String(r.likelihood)}·I{String(r.impact)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function RedFlagBody({ o }: { o: Record<string, unknown> }) {
  const grade = s(o.overall_grade);
  const flags = arr(o.flags) as Record<string, unknown>[];
  return (
    <>
      <Badge tone={grade === "clean" ? "up" : grade === "caution" ? "warn" : "down"}
             className="uppercase">{grade || "n/a"}</Badge>
      {flags.length === 0 ? (
        <p className="text-muted">No material accounting flags identified.</p>
      ) : (
        <ul className="space-y-1.5">
          {flags.slice(0, 6).map((f, i) => (
            <li key={i} className="text-muted">
              <span className={cn("mr-1.5 font-medium",
                s(f.severity) === "critical" ? "text-down"
                : s(f.severity) === "warn" ? "text-warn" : "text-fg")}>
                {s(f.code)}
              </span>
              {s(f.explanation)}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function GenericBody({ o }: { o: Record<string, unknown> }) {
  const paragraphs = Object.entries(o)
    .filter(([, v]) => typeof v === "string" && (v as string).length > 40)
    .slice(0, 4);
  const lists = Object.entries(o)
    .filter(([, v]) => Array.isArray(v) && (v as unknown[]).length > 0)
    .slice(0, 2);
  return (
    <>
      {paragraphs.map(([k, v]) => (
        <div key={k}>
          <div className="label mb-0.5">{k.replaceAll("_", " ")}</div>
          <p className="text-muted">{v as string}</p>
        </div>
      ))}
      {lists.map(([k, v]) => (
        <BulletBlock
          key={k}
          title={k.replaceAll("_", " ")}
          tone="text-accent"
          items={(v as unknown[]).map((item) =>
            typeof item === "string" ? item
            : s((item as Record<string, unknown>).point)
              || JSON.stringify(item).slice(0, 120))}
        />
      ))}
    </>
  );
}

function BulletBlock({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <div className="label mb-1">{title}</div>
      <ul className="space-y-1">
        {items.slice(0, 5).map((item, i) => (
          <li key={i} className="flex gap-2 text-muted">
            <span className={cn("mt-1.5 h-1 w-1 shrink-0 rounded-full bg-current", tone)} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
