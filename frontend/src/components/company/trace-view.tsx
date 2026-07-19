"use client";
/** Interactive audit-trace explorer: renders a CalcNode tree —
 *  formula → substituted values → result, expandable intermediates. This is
 *  the platform's "show your work" surface. */
import { ChevronRightIcon } from "@heroicons/react/24/outline";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";

import { ConfidenceMeter } from "@/components/ui/primitives";
import type { CalcNode } from "@/lib/api";
import { cn } from "@/lib/utils";

export function TraceView({ node, depth = 0 }: { node: CalcNode; depth?: number }) {
  const [open, setOpen] = useState(depth === 0);
  const hasChildren = node.intermediates.length > 0;

  return (
    <div className={cn(depth > 0 && "ml-4 border-l border-line pl-3")}>
      <button
        onClick={() => hasChildren && setOpen((v) => !v)}
        className={cn(
          "group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left",
          hasChildren && "hover:bg-surface-2",
        )}
      >
        <ChevronRightIcon
          className={cn(
            "mt-0.5 h-3 w-3 shrink-0 text-faint transition-transform",
            open && "rotate-90",
            !hasChildren && "invisible",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span className="text-xs font-medium">{node.label}</span>
            <span className="tnum font-mono text-xs text-accent">{node.result}</span>
            {node.unit && <span className="text-[10px] text-faint">{node.unit}</span>}
          </div>
          <div className="mt-0.5 font-mono text-[11px] text-muted">{node.formula}</div>
          {node.substitution && node.substitution !== node.formula && (
            <div className="mt-0.5 break-all font-mono text-[11px] text-faint">
              {node.substitution}
            </div>
          )}
        </div>
        <ConfidenceMeter value={node.confidence} className="mt-1 shrink-0" />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            {node.explanation && (
              <p className="ml-7 mt-1 max-w-2xl text-[11px] leading-relaxed text-muted">
                {node.explanation}
              </p>
            )}
            {node.assumptions.length > 0 && (
              <ul className="ml-7 mt-1 space-y-0.5">
                {node.assumptions.map((a, i) => (
                  <li key={i} className="text-[11px] text-warn">⚠ {a}</li>
                ))}
              </ul>
            )}
            {node.inputs.length > 0 && (
              <div className="ml-7 mt-2 overflow-hidden rounded-md border border-line">
                <table className="w-full text-[11px]">
                  <tbody>
                    {node.inputs.map((inp) => (
                      <tr key={inp.name} className="border-b border-line last:border-0">
                        <td className="px-2.5 py-1 font-mono text-muted">{inp.symbol}</td>
                        <td className="px-2.5 py-1 text-muted">{inp.name.replaceAll("_", " ")}</td>
                        <td className="tnum px-2.5 py-1 text-right font-mono">{inp.value}</td>
                        <td className="px-2.5 py-1 text-right text-faint">
                          {inp.source?.provider ?? ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {node.intermediates.map((child) => (
              <TraceView key={child.key} node={child} depth={depth + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
