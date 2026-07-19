"use client";
/** Watchlist workspace: tracked companies with live quotes and notes. */
import { TrashIcon } from "@heroicons/react/24/outline";
import Link from "next/link";

import { CompanyCard } from "@/components/company-card";
import { EmptyState, Panel, PanelHeader } from "@/components/ui/primitives";
import { useWorkspace } from "@/lib/store";

export default function WatchlistPage() {
  const { watchlist, toggleWatch, notes, setNote } = useWorkspace();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-lg font-semibold tracking-tight">Watchlist</h1>
      <p className="mt-1 text-xs text-muted">
        Tracked companies with live quotes. Notes stay on this device.
      </p>

      {watchlist.length === 0 ? (
        <Panel className="mt-6">
          <EmptyState
            title="Nothing tracked yet"
            detail="Search a company (⌘K) and press Watch on its dashboard."
            action={
              <Link href="/" className="text-xs text-accent hover:underline">
                Go to search →
              </Link>
            }
          />
        </Panel>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
          {watchlist.map((c) => (
            <div key={c.id} className="space-y-2">
              <CompanyCard company={c} />
              <Panel>
                <PanelHeader
                  title={`Notes — ${c.ticker}`}
                  right={
                    <button
                      onClick={() => toggleWatch(c)}
                      className="text-muted transition-colors hover:text-down"
                      title="Remove from watchlist"
                    >
                      <TrashIcon className="h-3.5 w-3.5" />
                    </button>
                  }
                />
                <textarea
                  value={notes[c.id] ?? ""}
                  onChange={(e) => setNote(c.id, e.target.value)}
                  placeholder="Analyst notes — thesis, levels, catalysts…"
                  className="h-20 w-full resize-none bg-transparent p-3 text-xs outline-none placeholder:text-faint"
                />
              </Panel>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
