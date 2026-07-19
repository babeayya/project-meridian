"use client";
/** Core UI primitives: hairline panels, badges, stats, skeletons. */
import { motion, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export function Panel({
  className, children, hover = false,
}: { className?: string; children: React.ReactNode; hover?: boolean }) {
  return (
    <div className={cn("panel", hover && "panel-hover", className)}>{children}</div>
  );
}

export function PanelHeader({
  title, right, className,
}: { title: React.ReactNode; right?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-center justify-between px-4 py-3 border-b border-line", className)}>
      <span className="label">{title}</span>
      {right}
    </div>
  );
}

type BadgeTone = "up" | "down" | "neutral" | "accent" | "warn";
const BADGE_TONES: Record<BadgeTone, string> = {
  up: "bg-up/10 text-up border-up/20",
  down: "bg-down/10 text-down border-down/20",
  neutral: "bg-surface-2 text-muted border-line",
  accent: "bg-accent/10 text-accent border-accent/20",
  warn: "bg-warn/10 text-warn border-warn/20",
};

export function Badge({
  tone = "neutral", children, className,
}: { tone?: BadgeTone; children: React.ReactNode; className?: string }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium tnum",
      BADGE_TONES[tone], className)}>
      {children}
    </span>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-surface-2", className)} />;
}

export function Stat({
  label, value, sub, className, valueClass,
}: { label: string; value: React.ReactNode; sub?: React.ReactNode;
     className?: string; valueClass?: string }) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <span className="label">{label}</span>
      <span className={cn("tnum font-mono text-[15px] font-medium", valueClass)}>{value}</span>
      {sub && <span className="text-[11px] text-muted">{sub}</span>}
    </div>
  );
}

/** Smoothly counts to a numeric value; renders via a formatter. */
export function CountUp({
  value, format, duration = 0.8, className,
}: { value: number; format: (n: number) => string; duration?: number; className?: string }) {
  const [display, setDisplay] = useState(0);
  const started = useRef(false);
  const from = useRef(0);

  useEffect(() => {
    const start = performance.now();
    const initial = started.current ? from.current : 0;
    started.current = true;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min((t - start) / (duration * 1000), 1);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(initial + (value - initial) * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration]);

  return <span className={cn("tnum", className)}>{format(display)}</span>;
}

/** Fades + slides content in when it enters the viewport. */
export function Reveal({
  children, delay = 0, className,
}: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 14 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay, ease: [0.21, 0.7, 0.35, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Confidence meter: 0..1 → hairline bar with grade color. */
export function ConfidenceMeter({ value, className }: { value: number; className?: string }) {
  const tone = value >= 0.75 ? "var(--up)" : value >= 0.5 ? "var(--warn)" : "var(--down)";
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-2">
        <motion.div
          className="h-full rounded-full"
          style={{ background: tone }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(value * 100)}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
      </div>
      <span className="tnum text-[11px] text-muted">{Math.round(value * 100)}%</span>
    </div>
  );
}

export function EmptyState({
  title, detail, action,
}: { title: string; detail?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-14 text-center">
      <span className="text-sm font-medium text-muted">{title}</span>
      {detail && <span className="max-w-md text-xs text-faint">{detail}</span>}
      {action}
    </div>
  );
}

export function Button({
  children, onClick, variant = "default", disabled, className, title,
}: {
  children: React.ReactNode; onClick?: () => void; disabled?: boolean;
  variant?: "default" | "primary" | "ghost"; className?: string; title?: string;
}) {
  return (
    <button
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium",
        "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
        variant === "default" && "border-line bg-surface-2 text-fg hover:border-line-strong",
        variant === "primary" && "border-accent/30 bg-accent/10 text-accent hover:bg-accent/20",
        variant === "ghost" && "border-transparent text-muted hover:bg-surface-2 hover:text-fg",
        className,
      )}
    >
      {children}
    </button>
  );
}
