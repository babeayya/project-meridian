/** Institutional number formatting: compact scales, signed deltas, tabular. */

const CURRENCY_SYMBOL: Record<string, string> = {
  USD: "$", INR: "₹", EUR: "€", GBP: "£", JPY: "¥", CAD: "C$", AUD: "A$",
};

export function currencySymbol(code?: string | null): string {
  return code ? CURRENCY_SYMBOL[code] ?? `${code} ` : "";
}

/** 416161000000 → "416.16B"; 12500 → "12.5K" */
export function compact(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `${(n / 1e12).toFixed(digits)}T`;
  if (abs >= 1e9) return `${(n / 1e9).toFixed(digits)}B`;
  if (abs >= 1e6) return `${(n / 1e6).toFixed(digits)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(digits)}K`;
  return n.toFixed(digits);
}

export function money(value: number | string | null | undefined,
                      currency?: string | null, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  return `${currencySymbol(currency)}${compact(value, digits)}`;
}

export function price(value: number | string | null | undefined,
                      currency?: string | null): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return `${currencySymbol(currency)}${n.toLocaleString("en-US", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`;
}

/** 0.0913 → "9.13%"; pass already-percent values with scaled=true */
export function pct(value: number | string | null | undefined,
                    opts: { signed?: boolean; scaled?: boolean; digits?: number } = {}): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  const v = opts.scaled ? n : n * 100;
  const sign = opts.signed && v > 0 ? "+" : "";
  return `${sign}${v.toFixed(opts.digits ?? 2)}%`;
}

export function ratio(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return `${n.toFixed(digits)}×`;
}

export function num(value: number | string | null | undefined, digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? parseFloat(value) : value;
  if (!isFinite(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function deltaClass(v: number | string | null | undefined): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  if (n === null || n === undefined || !isFinite(n) || n === 0) return "text-muted";
  return n > 0 ? "text-up" : "text-down";
}

/** Format a CalcNode value given its declared unit. */
export function byUnit(value: string, unit: string, currency?: string | null): string {
  if (unit === "%") return pct(value);
  if (unit === "x" || unit === "×") return ratio(value);
  if (unit === "days") return `${num(value, 0)}d`;
  if (unit?.includes("/share")) return price(value, currency);
  return num(value);
}
