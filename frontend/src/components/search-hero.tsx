"use client";
/** Landing hero: live company search against the resolve endpoint with a
 *  rotating placeholder and animated result list. */
import { ArrowRightIcon, MagnifyingGlassIcon } from "@heroicons/react/24/outline";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useResolve, useSelectCandidate } from "@/hooks/use-api";
import type { ResolveCandidate } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

const EXAMPLES = ["Apple", "Microsoft", "Reliance Industries", "NVIDIA", "TCS", "HDFC Bank"];

export function SearchHero() {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [placeholder, setPlaceholder] = useState("");
  const exampleIdx = useRef(0);
  const router = useRouter();
  const pushRecent = useWorkspace((s) => s.pushRecent);
  const { data, isFetching } = useResolve(debounced);
  const select = useSelectCandidate();

  // debounce live search
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  // typewriter placeholder cycling through real examples
  useEffect(() => {
    let char = 0;
    let deleting = false;
    const tick = setInterval(() => {
      const word = EXAMPLES[exampleIdx.current % EXAMPLES.length];
      if (!deleting) {
        char += 1;
        if (char > word.length + 14) deleting = true; // hold, then erase
      } else {
        char -= 2;
        if (char <= 0) {
          deleting = false;
          exampleIdx.current += 1;
        }
      }
      setPlaceholder(word.slice(0, Math.max(0, Math.min(char, word.length))));
    }, 90);
    return () => clearInterval(tick);
  }, []);

  const goto = (id: string, name: string, ticker: string, exchange: string) => {
    pushRecent({ id, name, ticker, exchange });
    router.push(`/company/${id}`);
  };

  const pick = async (c: ResolveCandidate) => {
    if (c.company_id) return goto(c.company_id, c.name, c.ticker, c.exchange);
    const res = await select.mutateAsync(c);
    goto(res.data.id, res.data.name, c.ticker, c.exchange);
  };

  const match = data?.data.match;
  const candidates = data?.data.candidates ?? [];
  const showResults = debounced.length >= 2 && (match || candidates.length > 0 || isFetching);

  return (
    <div className="relative mx-auto w-full max-w-2xl">
      <div className="group relative">
        <MagnifyingGlassIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-faint" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Search ${placeholder}▎`}
          className="w-full rounded-xl border border-line bg-surface px-12 py-4 text-[15px] shadow-2xl shadow-black/20 outline-none transition-colors placeholder:text-faint focus:border-accent/50"
          aria-label="Search any listed company"
        />
        {isFetching && (
          <span className="absolute right-4 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin rounded-full border-2 border-line border-t-accent" />
        )}
      </div>

      <AnimatePresence>
        {showResults && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.18 }}
            className="absolute inset-x-0 top-full z-30 mt-2 overflow-hidden rounded-xl border border-line-strong bg-surface shadow-2xl"
          >
            {match && (
              <ResultRow
                name={match.name}
                ticker={match.listings[0]?.ticker ?? "—"}
                exchange={match.listings[0]?.exchange ?? ""}
                primary
                onClick={() => goto(match.id, match.name,
                  match.listings[0]?.ticker ?? "", match.listings[0]?.exchange ?? "")}
              />
            )}
            {candidates.slice(0, 6).map((c) => (
              <ResultRow
                key={`${c.ticker}-${c.exchange}`}
                name={c.name}
                ticker={c.ticker}
                exchange={c.exchange}
                confidence={c.confidence}
                onClick={() => pick(c)}
              />
            ))}
            {!isFetching && !match && candidates.length === 0 && (
              <div className="px-4 py-4 text-center text-xs text-muted">No matches</div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ResultRow({
  name, ticker, exchange, confidence, primary, onClick,
}: {
  name: string; ticker: string; exchange: string;
  confidence?: number; primary?: boolean; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex w-full items-center gap-3 border-b border-line px-4 py-3 text-left transition-colors last:border-0 hover:bg-surface-2"
    >
      <span className="flex w-28 shrink-0 items-baseline gap-1.5">
        <span className="font-mono text-sm font-semibold">{ticker}</span>
        <span className="text-[10px] text-faint">{exchange}</span>
      </span>
      <span className="truncate text-sm">{name}</span>
      {primary && (
        <span className="ml-auto rounded bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent">
          Best match
        </span>
      )}
      {confidence !== undefined && !primary && (
        <span className="ml-auto tnum text-[10px] text-faint">
          {Math.round(confidence * 100)}%
        </span>
      )}
      <ArrowRightIcon className="h-3.5 w-3.5 shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100" />
    </button>
  );
}
