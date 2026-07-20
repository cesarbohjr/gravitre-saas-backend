"use client"

import { useState } from "react"
import { CaretDown, Info } from "@phosphor-icons/react"
import { cn } from "@/lib/utils"
import { ConfidenceBadge } from "./confidence-badge"

export function RecommendationExplanation({
  summary,
  confidence,
  advisoryOnly = true,
  sources,
  className,
  isEstimate,
}: {
  summary?: string | null
  confidence?: number | null
  advisoryOnly?: boolean
  sources?: Array<{ type?: string; label?: string }>
  className?: string
  /** Module C / STA-331: when API stamps estimate provenance, surface it on the badge. */
  isEstimate?: boolean
}) {
  const [open, setOpen] = useState(false)
  const safeSummary = (summary || "").trim() || "No explanation available yet."

  return (
    <div className={cn("rounded-xl border border-border/70 bg-card/50", className)}>
      <button
        type="button"
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-primary" weight="duotone" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="text-sm font-medium text-foreground">Why this recommendation</span>
          {!open ? (
            <span className="mt-0.5 block truncate text-sm text-muted-foreground">{safeSummary}</span>
          ) : null}
        </span>
        <ConfidenceBadge
          score={confidence}
          showScore={false}
          isEstimate={Boolean(isEstimate)}
          className="shrink-0"
        />
        <CaretDown
          className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="space-y-3 border-t border-border/60 px-4 py-3 text-sm">
          <p className="leading-relaxed text-foreground text-pretty">{safeSummary}</p>
          {advisoryOnly ? (
            <p className="rounded-lg border border-dashed border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-900 dark:text-amber-200">
              Advisory only — human approval is required before any write action executes.
            </p>
          ) : null}
          {sources && sources.length > 0 ? (
            <ul className="space-y-1 text-xs text-muted-foreground">
              {sources.map((source, index) => (
                <li key={`${source.type}-${index}`}>
                  Source: {source.label || source.type || "signal"}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
