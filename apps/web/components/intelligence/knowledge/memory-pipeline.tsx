"use client"

/** "How a memory is earned": the four-stage funnel and the auto-promote rule. */
import { ArrowDown, ArrowRight, SlidersHorizontal } from "@phosphor-icons/react"
import { GravitreSurface } from "@/components/gravitre/nodus-product/metric"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { MemoryPolicy } from "./use-org-memory"

type StageTone = "neutral" | "review" | "done"

const STAGE_TONE: Record<StageTone, { box: string; label: string }> = {
  neutral: { box: "border-divide bg-[color:var(--g-surface-1)]", label: "text-[color:var(--g-text-muted)]" },
  review: {
    box: "border-[color:var(--g-approval)]/30 bg-[color:var(--g-approval-soft)]",
    label: "text-[color:var(--g-approval)]",
  },
  done: {
    box: "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]",
    label: "text-[color:var(--g-brand-active)]",
  },
}

function Stage({
  index,
  label,
  value,
  hint,
  tone,
  title,
}: {
  index: string
  label: string
  value: number | null
  hint: string
  tone: StageTone
  title?: string
}) {
  const t = STAGE_TONE[tone]
  return (
    <div className={cn("flex min-w-0 flex-col gap-1.5 rounded-[var(--np-radius-md)] border p-4", t.box)} title={title}>
      <span className={cn("font-mono text-[11px] uppercase tracking-[0.06em]", t.label)}>
        {index} · {label}
      </span>
      <span className="text-[28px] font-semibold leading-none tabular-nums text-[color:var(--g-text-primary)]">
        {value ?? "—"}
      </span>
      <span className={TYPE.meta}>{hint}</span>
    </div>
  )
}

function StageArrow() {
  return (
    <span aria-hidden className="flex items-center justify-center text-[color:var(--g-text-disabled)]">
      <ArrowRight className="hidden h-4 w-4 lg:block" />
      <ArrowDown className="h-4 w-4 lg:hidden" />
    </span>
  )
}

function PolicyChip({ children, title }: { children: string; title: string }) {
  return (
    <span
      title={title}
      className="rounded-[7px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-2 py-1 font-mono text-xs tabular-nums text-[color:var(--g-text-primary)]"
    >
      {children}
    </span>
  )
}

export function MemoryPipeline({
  pipeline,
  policy,
  watchedAgents,
  agentsLoaded,
}: {
  pipeline: {
    observed: number | null
    repeating: number | null
    needsReview: number | null
    orgMemory: number | null
    repeatingIsPartial: boolean
  }
  policy: MemoryPolicy
  watchedAgents: number
  agentsLoaded: boolean
}) {
  const policyTitle = "Set by Gravitre. There is no setting to change this yet."
  return (
    <GravitreSurface className="space-y-5">
      <section aria-labelledby="memory-pipeline-heading" className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <h2 id="memory-pipeline-heading" className="text-lg font-semibold text-[color:var(--g-text-primary)]">
              How a memory is earned
            </h2>
            <p className={TYPE.bodyMuted}>
              Patterns that repeat across runs become candidates. You decide what the whole organization remembers.
            </p>
          </div>
          {agentsLoaded ? (
            <span
              className={cn(
                "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[13px]",
                watchedAgents > 0
                  ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)]"
                  : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-muted)]",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "h-[7px] w-[7px] rounded-full",
                  watchedAgents > 0 ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-text-disabled)]",
                )}
              />
              {watchedAgents > 0
                ? `Watching ${watchedAgents} ${watchedAgents === 1 ? "agent" : "agents"}`
                : "No agents to watch yet"}
            </span>
          ) : null}
        </div>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-[minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)_24px_minmax(0,1fr)] lg:items-center lg:gap-0">
          <Stage index="01" label="Observed" value={pipeline.observed} hint="Facts noticed during agent runs" tone="neutral" />
          <StageArrow />
          <Stage
            index="02"
            label="Repeating"
            value={pipeline.repeating}
            hint="Seen more than once, building confidence"
            tone="neutral"
            title={pipeline.repeatingIsPartial ? "Counted from the 200 most recent candidates" : undefined}
          />
          <StageArrow />
          <Stage index="03" label="Needs review" value={pipeline.needsReview} hint="Candidates waiting for a person" tone="review" />
          <StageArrow />
          <Stage index="04" label="Org memory" value={pipeline.orgMemory} hint="Used by every agent and answer" tone="done" />
        </div>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-4 py-3 text-[13px] text-[color:var(--g-text-secondary)]">
          <SlidersHorizontal className="h-4 w-4 text-[color:var(--g-text-muted)]" aria-hidden />
          <span>Auto-promote when seen</span>
          <PolicyChip title={policyTitle}>
            {policy.minOccurrences != null ? `${policy.minOccurrences} times` : "—"}
          </PolicyChip>
          <span>across</span>
          <PolicyChip title={policyTitle}>
            {policy.minDepartments != null ? `${policy.minDepartments} teams` : "—"}
          </PolicyChip>
          <span>with confidence above</span>
          <PolicyChip title="Gravitre does not use a confidence threshold for auto-promotion yet.">Not used</PolicyChip>
          <span className="flex-1" />
          <span className={TYPE.meta}>Everything else waits for review</span>
        </div>
      </section>
    </GravitreSurface>
  )
}
