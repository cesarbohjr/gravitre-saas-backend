"use client"

import { cn } from "@/lib/utils"

export type FleetSummaryCounts = {
  total: number
  working: number
  available: number
  idle: number
  failed: number
  tasksToday: number
}

/** AI Team summary — Working ≠ Available (config vs live work). */
export function FleetSummaryBar({
  counts,
  className,
}: {
  counts: FleetSummaryCounts
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-end justify-between gap-3 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] px-4 py-3 shadow-[var(--np-shadow)]",
        className,
      )}
    >
      <div>
        <p className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          AI Team
        </p>
        <p className="text-lg font-semibold tabular-nums text-[color:var(--g-text-primary)]">
          {counts.total} agents
        </p>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[color:var(--g-text-muted)]">
        <span className="inline-flex items-center gap-1.5" title="Currently executing work">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
          {counts.working} Working
        </span>
        <span className="inline-flex items-center gap-1.5" title="Enabled and ready">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          {counts.available} Available
        </span>
        <span className="inline-flex items-center gap-1.5" title="Enabled but not in live work">
          <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
          {counts.idle} Idle
        </span>
        {counts.failed > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-rose-700 dark:text-rose-300">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
            {counts.failed} Failed
          </span>
        ) : null}
      </div>
      <p className="text-sm tabular-nums text-[color:var(--g-text-primary)]">
        {counts.tasksToday}{" "}
        <span className="text-[color:var(--g-text-muted)]">tasks today</span>
      </p>
    </div>
  )
}
