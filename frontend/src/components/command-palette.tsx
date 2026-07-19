"use client";
/** ⌘K command palette: live company search (backend resolve), workspace
 *  navigation, theme + actions. Built on cmdk. */
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useResolve, useSelectCandidate } from "@/hooks/use-api";
import type { ResolveCandidate } from "@/lib/api";
import { useWorkspace } from "@/lib/store";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();
  const { watchlist, recent, theme, setTheme, pushRecent } = useWorkspace();
  const { data, isFetching } = useResolve(query, open);
  const select = useSelectCandidate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !isTyping(e))) {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    const onOpen = () => setOpen(true);
    document.addEventListener("keydown", onKey);
    document.addEventListener("open-command-palette", onOpen);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("open-command-palette", onOpen);
    };
  }, []);

  const goto = (id: string, name: string, ticker: string, exchange: string) => {
    pushRecent({ id, name, ticker, exchange });
    setOpen(false);
    setQuery("");
    router.push(`/company/${id}`);
  };

  const pick = async (c: ResolveCandidate) => {
    if (c.company_id) return goto(c.company_id, c.name, c.ticker, c.exchange);
    const res = await select.mutateAsync(c);
    goto(res.data.id, res.data.name, c.ticker, c.exchange);
  };

  if (!open) return null;

  const match = data?.data.match;
  const candidates = data?.data.candidates ?? [];

  return (
    <div
      className="no-print fixed inset-0 z-[70] flex items-start justify-center bg-black/50 pt-[14vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
    >
      <Command
        shouldFilter={false}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-line-strong bg-surface shadow-2xl"
        label="Command palette"
      >
        <Command.Input
          autoFocus
          value={query}
          onValueChange={setQuery}
          placeholder="Search any listed company — Apple, TCS, Reliance, NVDA…"
          className="w-full border-b border-line bg-transparent px-4 py-3.5 text-sm outline-none placeholder:text-faint"
        />
        <Command.List className="max-h-[380px] overflow-y-auto p-2">
          {isFetching && (
            <div className="px-3 py-2 text-xs text-muted">Searching live providers…</div>
          )}

          {match && (
            <Group heading="Match">
              <Item onSelect={() => goto(match.id, match.name,
                match.listings[0]?.ticker ?? "", match.listings[0]?.exchange ?? "")}>
                <TickerCell ticker={match.listings[0]?.ticker ?? "—"}
                            exchange={match.listings[0]?.exchange ?? ""} />
                <span className="truncate">{match.name}</span>
              </Item>
            </Group>
          )}

          {candidates.length > 0 && (
            <Group heading="Candidates">
              {candidates.slice(0, 7).map((c) => (
                <Item key={`${c.ticker}-${c.exchange}`} onSelect={() => pick(c)}>
                  <TickerCell ticker={c.ticker} exchange={c.exchange} />
                  <span className="truncate">{c.name}</span>
                  <span className="ml-auto tnum text-[10px] text-faint">
                    {Math.round(c.confidence * 100)}%
                  </span>
                </Item>
              ))}
            </Group>
          )}

          {query.length < 2 && recent.length > 0 && (
            <Group heading="Recent">
              {recent.map((r) => (
                <Item key={r.id} onSelect={() => goto(r.id, r.name, r.ticker, r.exchange)}>
                  <TickerCell ticker={r.ticker} exchange={r.exchange} />
                  <span className="truncate">{r.name}</span>
                </Item>
              ))}
            </Group>
          )}

          {query.length < 2 && watchlist.length > 0 && (
            <Group heading="Watchlist">
              {watchlist.slice(0, 5).map((w) => (
                <Item key={w.id} onSelect={() => goto(w.id, w.name, w.ticker, w.exchange)}>
                  <TickerCell ticker={w.ticker} exchange={w.exchange} />
                  <span className="truncate">{w.name}</span>
                </Item>
              ))}
            </Group>
          )}

          <Group heading="Actions">
            <Item onSelect={() => { setTheme(theme === "dark" ? "light" : "dark"); setOpen(false); }}>
              <span className="text-muted">Toggle {theme === "dark" ? "light" : "dark"} mode</span>
              <kbd className="ml-auto font-mono text-[10px] text-faint">T</kbd>
            </Item>
            <Item onSelect={() => { window.print(); setOpen(false); }}>
              <span className="text-muted">Export current view to PDF</span>
            </Item>
            <Item onSelect={() => { router.push("/watchlist"); setOpen(false); }}>
              <span className="text-muted">Open watchlist</span>
            </Item>
          </Group>

          {query.length >= 2 && !isFetching && !match && candidates.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted">
              No companies found for “{query}”
            </div>
          )}
        </Command.List>
      </Command>
    </div>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="[&_[cmdk-group-heading]]:label [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5"
    >
      {children}
    </Command.Group>
  );
}

function Item({ children, onSelect }: { children: React.ReactNode; onSelect: () => void }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-[13px] data-[selected=true]:bg-surface-2"
    >
      {children}
    </Command.Item>
  );
}

function TickerCell({ ticker, exchange }: { ticker: string; exchange: string }) {
  return (
    <span className="flex w-24 shrink-0 items-baseline gap-1.5">
      <span className="font-mono text-xs font-semibold">{ticker}</span>
      <span className="text-[10px] text-faint">{exchange}</span>
    </span>
  );
}

function isTyping(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement;
  return t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable;
}
