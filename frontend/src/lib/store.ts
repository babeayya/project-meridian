"use client";
/** Client-side persistence: watchlist, pins, recently viewed, theme. */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface TrackedCompany {
  id: string;
  name: string;
  ticker: string;
  exchange: string;
  currency?: string | null;
}

interface WorkspaceState {
  watchlist: TrackedCompany[];
  pinned: string[]; // company ids, subset of watchlist
  recent: TrackedCompany[];
  theme: "dark" | "light";
  notes: Record<string, string>; // company id -> analyst note
  toggleWatch: (c: TrackedCompany) => void;
  togglePin: (id: string) => void;
  pushRecent: (c: TrackedCompany) => void;
  setTheme: (t: "dark" | "light") => void;
  setNote: (id: string, text: string) => void;
}

export const useWorkspace = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      watchlist: [],
      pinned: [],
      recent: [],
      theme: "dark",
      notes: {},
      toggleWatch: (c) => {
        const { watchlist, pinned } = get();
        const exists = watchlist.some((w) => w.id === c.id);
        set({
          watchlist: exists ? watchlist.filter((w) => w.id !== c.id) : [...watchlist, c],
          pinned: exists ? pinned.filter((p) => p !== c.id) : pinned,
        });
      },
      togglePin: (id) => {
        const { pinned } = get();
        set({
          pinned: pinned.includes(id)
            ? pinned.filter((p) => p !== id)
            : [...pinned, id].slice(-6),
        });
      },
      pushRecent: (c) => {
        const recent = [c, ...get().recent.filter((r) => r.id !== c.id)].slice(0, 8);
        set({ recent });
      },
      setTheme: (theme) => {
        set({ theme });
        if (typeof document !== "undefined") {
          document.documentElement.classList.toggle("light", theme === "light");
        }
      },
      setNote: (id, text) => set({ notes: { ...get().notes, [id]: text } }),
    }),
    { name: "equity-workspace" },
  ),
);
