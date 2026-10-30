"use client"

/**
 * Models v2 — "Where models are used": one row per registry model, data
 * flowing left to right (Learns from → Model → Powers). Learns-from chips are
 * the model's linked training dataset; Powers is only claimed for deployed
 * models, and the registry does not report individual callers, so it says
 * what is true ("Available to workflows and agents") rather than naming any.
 */
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import "@/components/intelligence/shell/intel-motion.css"

export type ModelUsageRow = {
  id: string
  name: string
  live: boolean
  learnsFrom: string[]
  /** Shown only with "Show technical details". */
  technical?: string | null
}

function Connector({ live }: { live: boolean }) {
  // The design's connector: moving dashes while live, a dotted line when not.
  return <div className={cn("hidden md:block", live ? "ig-flow" : "ig-idle")} aria-hidden />
}

const COLUMN_LABEL = "font-mono text-[10px] uppercase tracking-[0.1em] text-[color:var(--g-text-muted)]"

export function ModelUsageTopology({
  rows,
  showTechnical = false,
  className,
}: {
  rows: ModelUsageRow[]
  showTechnical?: boolean
  className?: string
}) {
  return (
    <section
      aria-labelledby="model-usage-heading"
      className={cn(
        "space-y-4 rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-5 sm:p-6",
        className,
      )}
      data-review-surface="models-lineage"
    >
      <div className="space-y-1">
        <h2 id="model-usage-heading" className={TYPE.cardTitle}>
          Where models are used
        </h2>
        <p className={TYPE.bodyMuted}>
          Data flows left to right. Moving dashes mean the model is live and taking requests.
        </p>
      </div>

      {rows.length === 0 ? (
        <p className={cn(TYPE.meta, "rounded-[var(--g-radius-tile)] border border-dashed border-[color:var(--g-border-default)] px-4 py-6 text-center")}>
          Models appear here once they are registered. What they power is shown only after they go live.
        </p>
      ) : (
        <div className="grid grid-cols-1 items-center gap-x-0 gap-y-3 md:grid-cols-[minmax(0,1fr)_56px_minmax(0,1fr)_56px_minmax(0,1fr)]">
          <span className={cn(COLUMN_LABEL, "hidden md:block")}>Learns from</span>
          <span className="hidden md:block" aria-hidden />
          <span className={cn(COLUMN_LABEL, "hidden md:block")}>Model</span>
          <span className="hidden md:block" aria-hidden />
          <span className={cn(COLUMN_LABEL, "hidden md:block")}>Powers</span>

          {rows.map((row) => (
            <div key={row.id} className="contents">
              <div className="flex flex-wrap gap-1.5 pt-2 first:pt-0 md:pt-0">
                <span className={cn(COLUMN_LABEL, "w-full md:hidden")}>Learns from</span>
                {row.learnsFrom.length > 0 ? (
                  row.learnsFrom.map((source) => (
                    <span
                      key={source}
                      className="rounded-md border border-[color:var(--g-border-subtle)] px-2 py-1 text-xs text-[color:var(--g-text-primary)]"
                    >
                      {source}
                    </span>
                  ))
                ) : (
                  <span className={TYPE.meta}>No training data linked</span>
                )}
              </div>
              <div className="px-2">
                <Connector live={row.live} />
              </div>
              <div
                className={cn(
                  "flex min-w-0 items-center gap-2.5 rounded-[var(--g-radius-tile)] px-3.5 py-2.5",
                  row.live
                    ? "border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]"
                    : "border border-dashed border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)]",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "h-2 w-2 shrink-0 rounded-full",
                    row.live ? "ig-live bg-[color:var(--g-brand)]" : "bg-[color:var(--g-text-disabled)]",
                  )}
                />
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block truncate text-sm font-medium",
                      row.live ? "text-[color:var(--g-text-primary)]" : "text-[color:var(--g-text-secondary)]",
                    )}
                  >
                    {row.name}
                  </span>
                  {showTechnical && row.technical ? (
                    <span className={cn(TYPE.mono, "block truncate")}>{row.technical}</span>
                  ) : null}
                </span>
                <span className="sr-only">{row.live ? "Live" : "Not live"}</span>
              </div>
              <div className="px-2">
                <Connector live={row.live} />
              </div>
              <div className="flex flex-wrap gap-1.5 pb-2 md:pb-0">
                <span className={cn(COLUMN_LABEL, "w-full md:hidden")}>Powers</span>
                {row.live ? (
                  <span className="rounded-md bg-[color:var(--g-surface-2)] px-2 py-1 text-xs text-[color:var(--g-text-primary)]">
                    Available to workflows and agents
                  </span>
                ) : (
                  <span className={TYPE.meta}>Not deployed yet</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
