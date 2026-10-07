"use client"

import Link from "next/link"
import { APP_ROUTES } from "@/lib/app-routes"
import type { FlowLearning } from "@/components/intelligence/overview/flow-model"

/** "What Gravitre is learning": patterns still being reinforced, each traceable on the map. */
export function LearningCards({
  learnings,
  example,
  reinforced,
  onTrace,
}: {
  learnings: FlowLearning[]
  example: boolean
  /** Example mode keeps its own live reinforcement counter. */
  reinforced?: Record<string, number>
  onTrace: (nodeId: string) => void
}) {
  return (
    <section aria-labelledby="overview-learning-heading" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id="overview-learning-heading" className="text-lg font-semibold text-foreground">
            What Gravitre is learning
          </h2>
          <p className="text-sm text-[color:var(--g-text-secondary)]">
            Patterns getting stronger with every interaction. Confirm one to make it org memory.
          </p>
        </div>
        <Link
          href={APP_ROUTES.intelligenceMemory}
          className="text-[13px] font-medium text-[color:var(--g-brand-active,var(--g-brand))] underline-offset-2 hover:underline"
        >
          Review in Memory →
        </Link>
      </div>
      {learnings.length === 0 ? (
        <p className="rounded-[var(--np-radius-md)] border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-4 py-6 text-sm text-[color:var(--g-text-muted)]">
          Nothing is being reinforced yet. Patterns show up here once Gravitre sees the same thing repeat across runs.
        </p>
      ) : (
        <div className="grid gap-3 lg:grid-cols-3">
          {learnings.map((l) => {
            const count = example ? (reinforced?.[l.nodeId] ?? l.reinforced) : l.reinforced
            // Example confidence rises with reinforcement, as in the design; live uses the recorded value only.
            const conf = example && count != null ? Math.min(0.97, 0.55 + count * 0.012) : l.confidence
            return (
              <article
                key={l.id}
                className="flex flex-col gap-3 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-[4px] bg-[color:var(--g-approval-soft)] px-1.5 py-0.5 text-[11px] font-medium text-[color:var(--g-approval)]">
                    Learning
                  </span>
                  <span className="font-mono text-[11px] text-[color:var(--g-text-muted)]">
                    {count ? `reinforced ${count}×` : "not reinforced yet"}
                  </span>
                </div>
                <h3 className="line-clamp-2 text-base font-semibold text-foreground">{l.label}</h3>
                <p className="line-clamp-3 flex-1 text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">{l.desc}</p>
                <div className="flex items-center gap-2.5" title={conf == null ? "No confidence recorded for this pattern yet" : undefined}>
                  <span
                    className="h-1.5 flex-1 overflow-hidden rounded-full bg-[color:var(--g-approval-soft)]"
                    role="meter"
                    aria-label="Confidence"
                    aria-valuemin={0}
                    aria-valuemax={1}
                    aria-valuenow={conf ?? undefined}
                    aria-valuetext={conf == null ? "No confidence recorded" : conf.toFixed(2)}
                  >
                    <span className="block h-full rounded-full bg-[color:var(--g-approval)]" style={{ width: `${Math.round((conf ?? 0) * 100)}%` }} />
                  </span>
                  <span className="font-mono text-xs tabular-nums text-foreground">{conf == null ? "—" : conf.toFixed(2)}</span>
                </div>
                <button
                  type="button"
                  onClick={() => onTrace(l.nodeId)}
                  className="inline-flex min-h-9 self-start items-center rounded-[var(--np-radius-sm,8px)] border border-[color:var(--g-border-default)] px-3 text-[13px] font-medium text-foreground transition-colors hover:bg-[color:var(--g-surface-2)]"
                >
                  Trace on map
                </button>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
