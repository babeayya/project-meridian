"use client";
import {
  BookmarkIcon,
  CommandLineIcon,
  MagnifyingGlassIcon,
  MoonIcon,
  SunIcon,
} from "@heroicons/react/24/outline";
import { motion, useScroll, useTransform } from "framer-motion";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useProviderHealth } from "@/hooks/use-api";
import { useWorkspace } from "@/lib/store";
import { cn } from "@/lib/utils";

export function openPalette() {
  document.dispatchEvent(new CustomEvent("open-command-palette"));
}

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, setTheme, watchlist } = useWorkspace();
  const { data: health } = useProviderHealth();
  const { scrollY } = useScroll();
  const bg = useTransform(scrollY, [0, 60], ["rgba(0,0,0,0)", "rgba(0,0,0,0.001)"]);

  const providersUp = health?.providers?.filter((p) => p.breaker === "closed").length ?? 0;
  const providersTotal = health?.providers?.length ?? 0;

  return (
    <motion.header
      style={{ backgroundColor: bg }}
      className={cn(
        "no-print sticky top-0 z-50 border-b border-line",
        "backdrop-blur-xl bg-bg/80 supports-[backdrop-filter]:bg-bg/60",
      )}
    >
      <div className="mx-auto flex h-12 max-w-7xl items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="flex h-5 w-5 items-center justify-center rounded bg-accent/15 text-accent">
            <span className="block h-2 w-2 rotate-45 rounded-[2px] bg-accent" />
          </span>
          <span className="text-[13px] font-semibold tracking-tight">Meridian</span>
          <span className="label mt-0.5 hidden sm:block">Equity Research</span>
        </Link>

        <nav className="ml-4 hidden items-center gap-1 md:flex">
          <NavLink href="/" active={pathname === "/"}>Markets</NavLink>
          <NavLink href="/watchlist" active={pathname === "/watchlist"}>
            Watchlist{watchlist.length > 0 && (
              <span className="ml-1 tnum text-[10px] text-faint">{watchlist.length}</span>
            )}
          </NavLink>
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {providersTotal > 0 && (
            <span
              className="hidden items-center gap-1.5 text-[10px] text-muted lg:flex"
              title={`${providersUp}/${providersTotal} data providers healthy`}
            >
              <span className={cn("live-dot h-1.5 w-1.5 rounded-full",
                providersUp === providersTotal ? "bg-up" : "bg-warn")} />
              {providersUp}/{providersTotal} feeds
            </span>
          )}

          <button
            onClick={openPalette}
            className={cn(
              "flex items-center gap-2 rounded-md border border-line bg-surface-2 px-2.5 py-1.5",
              "text-xs text-muted transition-colors hover:border-line-strong hover:text-fg",
            )}
          >
            <MagnifyingGlassIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:block">Search companies…</span>
            <kbd className="hidden items-center gap-0.5 rounded border border-line bg-bg px-1 py-px font-mono text-[10px] text-faint sm:flex">
              <CommandLineIcon className="h-2.5 w-2.5" />K
            </kbd>
          </button>

          <button
            onClick={() => router.push("/watchlist")}
            className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-fg md:hidden"
            aria-label="Watchlist"
          >
            <BookmarkIcon className="h-4 w-4" />
          </button>

          <button
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            className="rounded-md p-1.5 text-muted transition-colors hover:bg-surface-2 hover:text-fg"
            aria-label="Toggle theme"
          >
            {theme === "dark"
              ? <SunIcon className="h-4 w-4" />
              : <MoonIcon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </motion.header>
  );
}

function NavLink({
  href, active, children,
}: { href: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
        active ? "bg-surface-2 text-fg" : "text-muted hover:text-fg",
      )}
    >
      {children}
    </Link>
  );
}
