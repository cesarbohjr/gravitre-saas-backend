"use client"

import type { IntelligenceLensMetrics, IntelligenceMapLens } from "./intelligence-map-lens"
import { INTELLIGENCE_MAP_LENSES } from "./intelligence-map-lens"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function IntelligenceLensBar({
  activeLens,
  onLensChange,
  metrics,
  className,
}: {
  activeLens: IntelligenceMapLens
  onLensChange: (lens: IntelligenceMapLens) => void
  metrics: IntelligenceLensMetrics
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-stretch justify-center gap-1 rounded-[var(--np-radius-lg)] border border-divide/80 bg-[color:var(--g-surface-1)]/90 p-1 backdrop-blur-sm",
        className,
      )}
      role="tablist"
      aria-label="Intelligence map lenses"
    >
      {INTELLIGENCE_MAP_LENSES.map((lens) => {
        const active = activeLens === lens.id
        const stat = metrics[lens.id]
        return (
          <button
            key={lens.id}
            type="button"
            role="tab"
            aria-selected={active}
            aria-controls="intelligence-map-canvas"
            title={lens.description}
            onClick={() => onLensChange(lens.id)}
            className={cn(
              "min-w-[7.5rem] flex-1 rounded-[var(--np-radius-md)] px-3 py-2 text-left transition-colors",
              active
                ? "bg-[color:var(--g-intelligence-surface)] shadow-sm ring-1 ring-[color:var(--g-brand-border)]"
                : "hover:bg-[color:var(--g-surface-2)]",
            )}
          >
            <span
              className={cn(
                TYPE.eyebrow,
                "block text-[10px]",
                active ? "text-[color:var(--g-intelligence)]" : "text-muted-foreground",
              )}
            >
              {lens.label}
            </span>
            <span
              className={cn(
                "mt-0.5 block text-lg font-semibold tabular-nums",
                stat.value === "—"
                  ? "text-muted-foreground"
                  : "text-[color:var(--g-text-primary)]",
              )}
              aria-busy={stat.value === "—" && stat.hint.includes("Loading")}
            >
              {stat.value}
            </span>
            <span className={cn(TYPE.meta, "mt-0.5 line-clamp-1")}>{stat.hint}</span>
          </button>
        )
      })}
    </div>
  )
}
