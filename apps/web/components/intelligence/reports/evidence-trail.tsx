"use client"

import Link from "next/link"
import { useState } from "react"
import { toast } from "sonner"
import type { OutcomeAttributionPath } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { RADIUS, TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  TRAIL_STEP_CONTINUES,
  TRAIL_STEP_FILL,
  TRAIL_STEP_LABEL,
  TRAIL_STEP_MISSING_TEXT,
  formatRecordedAt,
  toTrailSteps,
  trailHeadline,
} from "./report-model"

const LINK_PRIMARY =
  "inline-flex min-h-11 items-center rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-active)] px-3 text-sm font-medium text-white hover:bg-[color:var(--g-brand-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-9"
const LINK_OUTLINE =
  "inline-flex min-h-11 items-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] bg-background px-3 text-sm font-medium text-foreground hover:border-[color:var(--g-border-strong)] hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-9"

export function EvidenceTrail({
  path,
  loading,
}: {
  path: OutcomeAttributionPath | null
  loading: boolean
}) {
  const steps = toTrailSteps(path)
  const presentCount = steps.filter((s) => s.present).length
  const lastPresent = [...steps].reverse().find((s) => s.present)
  const [picked, setPicked] = useState<number | null>(null)
  const selectedN = picked ?? lastPresent?.n ?? 1
  const current = steps.find((s) => s.n === selectedN) ?? steps[0]
  const firstMissing = steps.find((s) => !s.present)
  const headline = trailHeadline(steps, path)

  async function copyRecord(id: string) {
    try {
      await navigator.clipboard.writeText(id)
      toast.success("Source record copied")
    } catch {
      toast.error("Could not copy. Select the id and copy it instead.")
    }
  }

  return (
    <section
      aria-labelledby="reports-trail-heading"
      className={cn(RADIUS.panel, "border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4 sm:p-6")}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className={TYPE.eyebrow}>Evidence trail · latest outcome</p>
          <h2 id="reports-trail-heading" className={cn(TYPE.cardTitle, "mt-1 text-lg sm:text-xl")}>
            {loading && !path ? "Loading evidence trail…" : headline ?? "No evidence trail yet"}
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1")}>
            {steps.length
              ? "How this result came about, step by step. Select a step to see the proof behind it."
              : loading
                ? "Reading the latest outcome from your live data."
                : "When Gravitre records a signal, forecast or outcome, the trail behind it appears here."}
          </p>
        </div>
        {steps.length ? (
          <span className="inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-3 py-1 text-xs text-[color:var(--g-text-secondary)]">
            <span className="font-semibold tabular-nums text-[color:var(--g-text-primary)]">
              {presentCount} / {steps.length}
            </span>
            steps with evidence
          </span>
        ) : null}
      </div>

      {steps.length && current ? (
        <>
          <ol className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7" aria-label="Evidence steps">
            {steps.map((step, index) => {
              const on = step.n === selectedN
              const next = steps[index + 1]
              return (
                <li key={step.kind} className="min-w-0">
                  <button
                    type="button"
                    aria-pressed={on}
                    onClick={() => setPicked(step.n)}
                    className={cn(
                      RADIUS.card,
                      "flex h-full w-full min-w-0 flex-col gap-2 border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      step.present ? "border-solid" : "border-dashed",
                      on
                        ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand-surface)] ring-2 ring-[color:var(--g-brand-soft)]"
                        : step.present
                          ? "border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] hover:border-[color:var(--g-border-strong)]"
                          : "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)]/50 hover:border-[color:var(--g-border-strong)]",
                    )}
                  >
                    <span className="flex items-center gap-2" aria-hidden>
                      <span
                        className={cn(
                          "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums",
                          step.present
                            ? "border-[color:var(--g-brand-active)] bg-[color:var(--g-brand-active)] text-white"
                            : "border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)] text-[color:var(--g-text-muted)]",
                        )}
                      >
                        {step.n}
                      </span>
                      <span
                        className={cn(
                          "h-0.5 flex-1 rounded-full",
                          !next
                            ? "bg-transparent"
                            : step.present && next.present
                              ? "bg-[color:var(--g-brand-active)]"
                              : "bg-[color:var(--g-border-subtle)]",
                        )}
                      />
                    </span>
                    <span className={cn(TYPE.meta, "font-mono tracking-wide")}>
                      {TRAIL_STEP_LABEL[step.kind]}
                    </span>
                    <span
                      className={cn(
                        "line-clamp-3 text-sm font-medium",
                        step.present ? "text-[color:var(--g-text-primary)]" : "text-[color:var(--g-text-muted)]",
                      )}
                    >
                      {step.label}
                    </span>
                    <span className="sr-only">{step.present ? "Evidence found" : "No verified evidence yet"}</span>
                  </button>
                </li>
              )
            })}
          </ol>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div className={cn(RADIUS.card, "bg-[color:var(--g-surface-2)] p-4 sm:p-5")} aria-live="polite">
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn(TYPE.meta, "font-mono tracking-wide")}>Step {current.n}</span>
                <span
                  className={cn(
                    RADIUS.tag,
                    "px-2 py-0.5 text-xs font-medium",
                    current.present
                      ? "bg-[color:var(--g-brand-soft)] text-[color:var(--g-brand-active)]"
                      : "bg-[color:var(--g-surface-3)] text-[color:var(--g-text-secondary)]",
                  )}
                >
                  {current.present ? "Evidence found" : "No verified evidence yet"}
                </span>
              </div>
              <h3 className={cn(TYPE.cardTitle, "mt-3 text-lg")}>{TRAIL_STEP_LABEL[current.kind]}</h3>
              <p className={cn(TYPE.body, "mt-2")}>
                {current.present ? current.label : TRAIL_STEP_MISSING_TEXT[current.kind]}
              </p>
              {current.present ? (
                current.proof.length ? (
                  <div className="mt-4">
                    <p className={cn(TYPE.meta, "font-mono tracking-wide")}>Proof</p>
                    <blockquote className="mt-1.5 space-y-1 rounded-[var(--np-radius-md)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-4 py-3 text-sm text-[color:var(--g-text-primary)]">
                      {current.proof.map((line) => (
                        <p key={line}>{line}</p>
                      ))}
                    </blockquote>
                  </div>
                ) : (
                  <p className={cn(TYPE.meta, "mt-4")}>The source record is the proof for this step.</p>
                )
              ) : (
                <p className="mt-4 flex items-start gap-2 rounded-[var(--np-radius-md)] border border-dashed border-[color:var(--g-brand-border)] bg-[color:var(--g-surface-1)] px-4 py-3 text-sm text-[color:var(--g-text-secondary)]">
                  <span aria-hidden className="mt-0.5 text-[color:var(--g-brand-active)]">✦</span>
                  {TRAIL_STEP_FILL[current.kind]}
                </p>
              )}
            </div>

            <div className={cn(RADIUS.card, "border border-[color:var(--g-border-subtle)] p-4 sm:p-5")}>
              <p className={cn(TYPE.meta, "font-mono tracking-wide")}>Source record</p>
              <div className="mt-2 flex min-w-0 flex-wrap items-center gap-2">
                <code className="min-w-0 break-all rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-2 py-1 font-mono text-xs text-[color:var(--g-text-primary)]">
                  {current.sourceRecordId ?? "None yet"}
                </code>
                {current.sourceRecordId ? (
                  <button
                    type="button"
                    onClick={() => copyRecord(current.sourceRecordId!)}
                    className="inline-flex min-h-11 items-center rounded-[var(--np-radius-md)] border border-[color:var(--g-border-default)] px-2.5 text-xs font-medium hover:bg-[color:var(--g-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-7"
                    aria-label="Copy source record id"
                  >
                    Copy
                  </button>
                ) : null}
              </div>
              <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-8 gap-y-2 text-sm">
                <dt className="text-[color:var(--g-text-muted)]">Recorded</dt>
                <dd className="text-[color:var(--g-text-primary)]">{formatRecordedAt(current.recordedAt)}</dd>
                <dt className="text-[color:var(--g-text-muted)]">From</dt>
                <dd className="text-[color:var(--g-text-primary)]">{current.from ?? "—"}</dd>
              </dl>
              <div className="mt-4 border-t border-[color:var(--g-border-subtle)] pt-4">
                <p className={TYPE.meta}>
                  {!firstMissing
                    ? "Every step on this trail has evidence."
                    : firstMissing.n === 1
                      ? `The trail starts once ${TRAIL_STEP_CONTINUES[firstMissing.kind]}.`
                      : `The trail stops at step ${firstMissing.n - 1}. It continues once ${TRAIL_STEP_CONTINUES[firstMissing.kind]}.`}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Link href={APP_ROUTES.intelligencePredictive} className={LINK_PRIMARY}>
                    Fix it in Forecasts
                  </Link>
                  <Link href={APP_ROUTES.intelligencePerformance} className={LINK_OUTLINE}>
                    See impact
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  )
}
