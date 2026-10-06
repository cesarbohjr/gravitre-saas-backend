"use client"

import { cn } from "@/lib/utils"
import type { AgentRuntimeState } from "@/components/agents/fleet-v4/types"

export type WorkforceCounts = {
  executing: number
  available: number
  failed: number
  idle: number
}

type FilterableState = Extract<AgentRuntimeState, "executing" | "available" | "failed" | "idle">

const CHIPS: { id: FilterableState; label: string; tone: string }[] = [
  { id: "executing", label: "Executing", tone: "bg-[color:var(--signal-500)]" },
  { id: "failed", label: "Needs attention", tone: "bg-destructive" },
  { id: "available", label: "Available", tone: "bg-[color:var(--g-emerald)]" },
  { id: "idle", label: "Idle", tone: "bg-[color:var(--g-text-muted)]" },
]

function plural(n: number, one: string, many: string) {
  return `${n} ${n === 1 ? one : many}`
}

export function workforceBriefingSentence(counts: WorkforceCounts, total: number): string {
  if (total === 0) return "No teammates yet."
  const verb = (n: number) => (n === 1 ? "is" : "are")
  const parts: string[] = []
  if (counts.failed > 0) parts.push(`${plural(counts.failed, "agent needs", "agents need")} your attention`)
  parts.push(
    counts.executing > 0
      ? `${counts.executing} ${verb(counts.executing)} executing right now`
      : "nobody is executing right now",
  )
  if (counts.available > 0) parts.push(`${counts.available} ${verb(counts.available)} available`)
  const sentence = parts.join(", ")
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}. ${plural(total, "teammate", "teammates")} in total.`
}

/**
 * The roster's opening line: what the workforce is doing, in one sentence,
 * with status chips that double as filters. Counts come straight from runtime state.
 */
export function WorkforceBriefing({
  counts,
  total,
  active,
  onSelect,
  className,
}: {
  counts: WorkforceCounts
  total: number
  active: string | null
  onSelect: (state: FilterableState | null) => void
  className?: string
}) {
  return (
    <section
      aria-label="Workforce briefing"
      data-workforce-briefing=""
      className={cn("flex flex-col gap-3 border-b border-divide px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]", className)}
    >
      <p className="text-pretty text-[15px] leading-relaxed text-[color:var(--g-text-primary)]">
        {workforceBriefingSentence(counts, total)}
      </p>
      <div role="group" aria-label="Filter by status" className="flex flex-wrap gap-2">
        {CHIPS.map((chip) => {
          const count = counts[chip.id]
          const selected = active === chip.id
          if (count === 0 && !selected) return null
          return (
            <button
              key={chip.id}
              type="button"
              aria-pressed={selected}
              onClick={() => onSelect(selected ? null : chip.id)}
              className={cn(
                "inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                selected
                  ? "border-[color:var(--g-emerald)] bg-[color:var(--g-emerald-pale)] text-[color:var(--g-text-primary)]"
                  : "border-[color:var(--g-border-default)] text-[color:var(--g-text-secondary)]",
              )}
            >
              <span aria-hidden className={cn("size-2 rounded-full", chip.tone, chip.id === "executing" && "motion-safe:animate-pulse")} />
              <span className="tabular-nums">{count}</span>
              {chip.label}
            </button>
          )
        })}
      </div>
    </section>
  )
}
