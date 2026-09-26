"use client"

/**
 * UX/UI 3.0 Plus — Activity A1 TRACE rail + story (optional A2 timeline).
 * Renders only stages present on the BusinessOutcome DTO — no invented TRACE.
 */

import { useMemo, useState } from "react"
import Link from "next/link"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import type { BusinessOutcomeDto } from "@/components/gravitre/business-outcome/business-outcome-view"
import { EvidenceChip, grammarToneForStepStatus } from "@/components/gravitre/creative-grammar"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export type ActivityTraceStage = {
  id: string
  label: string
  status: string
  summary?: string | null
  evidenceUrl?: string | null
  agentName?: string | null
  evidenceLabels?: string[]
}

const TRACE_CANONICAL = [
  "INTENT",
  "PLAN",
  "AGENT",
  "TOOL",
  "ACTION",
  "RESULT",
  "VERIFICATION",
  "OUTCOME",
] as const

function mapStepStatus(raw?: string | null): string {
  const s = (raw || "").toLowerCase()
  if (!s) return "pending"
  if (s.includes("fail") || s.includes("error") || s.includes("reject")) return "failed"
  if (s.includes("wait") || s.includes("approval") || s.includes("pending")) return "awaiting_approval"
  if (s.includes("run") || s.includes("progress") || s.includes("active")) return "running"
  if (s.includes("verif") || s.includes("complete") || s.includes("success") || s.includes("done") || s.includes("approved"))
    return "completed"
  return s
}

function classifyLabel(label: string): (typeof TRACE_CANONICAL)[number] | null {
  const u = label.toUpperCase()
  for (const stage of TRACE_CANONICAL) {
    if (u.includes(stage)) return stage
  }
  if (u.includes("INTENT") || u.includes("REQUEST")) return "INTENT"
  if (u.includes("PLAN") || u.includes("ROUTE")) return "PLAN"
  if (u.includes("AGENT")) return "AGENT"
  if (u.includes("TOOL") || u.includes("CONNECTOR")) return "TOOL"
  if (u.includes("ACTION") || u.includes("WRITE") || u.includes("EXECUTE")) return "ACTION"
  if (u.includes("RESULT") || u.includes("RESPONSE")) return "RESULT"
  if (u.includes("VERIFY") || u.includes("CHECK") || u.includes("READ-AFTER")) return "VERIFICATION"
  if (u.includes("OUTCOME") || u.includes("BUSINESS")) return "OUTCOME"
  return null
}

/** Build TRACE stages from real outcome fields only. */
export function buildActivityTraceStages(outcome: BusinessOutcomeDto): ActivityTraceStage[] {
  const timeline = outcome.sections?.timeline ?? []
  const stages: ActivityTraceStage[] = []

  if (timeline.length > 0) {
    for (let i = 0; i < timeline.length; i++) {
      const step = timeline[i]
      const rawLabel = String(step.label || `Step ${i + 1}`)
      const canonical = classifyLabel(rawLabel)
      stages.push({
        id: `tl-${step.index ?? i}`,
        label: canonical ?? rawLabel,
        status: mapStepStatus(step.status),
        summary: step.summary ?? null,
        evidenceUrl: step.evidenceUrl ?? null,
        agentName: step.agentName ?? null,
        evidenceLabels: step.evidenceUrl ? ["Evidence link"] : undefined,
      })
    }
  }

  const verification = outcome.sections?.verification
  if (verification) {
    const already = stages.some((s) => s.label === "VERIFICATION")
    if (!already) {
      stages.push({
        id: "verification",
        label: "VERIFICATION",
        status: verification.verified
          ? "completed"
          : verification.checkFailed
            ? "failed"
            : verification.confidence === "verified"
              ? "completed"
              : verification.confidence === "accepted_unproven"
                ? "awaiting_approval"
                : "pending",
        summary: verification.detail || verification.finding || verification.method || null,
        evidenceLabels: verification.method ? [verification.method] : undefined,
      })
    }
  }

  if (outcome.title || outcome.status) {
    const already = stages.some((s) => s.label === "OUTCOME")
    if (!already) {
      stages.push({
        id: "outcome",
        label: "OUTCOME",
        status: mapStepStatus(outcome.status || outcome.lifecycleState),
        summary: outcome.sections?.summary || outcome.title || null,
        evidenceLabels: outcome.sections?.evidence?.integration
          ? [String(outcome.sections.evidence.integration)]
          : undefined,
      })
    }
  }

  return stages
}

export function ActivityTracePanel({
  outcome,
  className,
}: {
  outcome: BusinessOutcomeDto
  className?: string
}) {
  const reduceMotion = useReducedMotion()
  const stages = useMemo(() => buildActivityTraceStages(outcome), [outcome])
  const [view, setView] = useState<"story" | "timeline">("story")
  const [activeId, setActiveId] = useState<string | null>(null)
  const active = stages.find((s) => s.id === (activeId ?? stages[stages.length - 1]?.id))

  if (stages.length === 0) {
    return (
      <div className={cn("rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-canvas)] p-4", className)} data-testid="activity-trace-empty">
        <p className={TYPE.eyebrow}>Trace</p>
        <p className={cn(TYPE.bodyMuted, "mt-2 text-sm")}>
          No recorded TRACE stages on this outcome. Do not invent a waterfall.
        </p>
        {outcome.runId ? (
          <Button type="button" size="sm" variant="outline" className="mt-3" asChild>
            <Link href={`/runs/${outcome.runId}?trace=1`}>Open run TRACE</Link>
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <div className={cn("space-y-3", className)} data-testid="activity-trace-a1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className={TYPE.eyebrow}>Execution trace</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            {stages.length} recorded stage{stages.length === 1 ? "" : "s"} · real outcome data
          </p>
        </div>
        <div className="flex gap-1">
          <Button
            type="button"
            size="sm"
            variant={view === "story" ? "secondary" : "outline"}
            onClick={() => setView("story")}
          >
            Story
          </Button>
          <Button
            type="button"
            size="sm"
            variant={view === "timeline" ? "secondary" : "outline"}
            onClick={() => setView("timeline")}
            data-testid="activity-a2-timeline"
          >
            Timeline
          </Button>
        </div>
      </div>

      {view === "timeline" ? (
        <div
          className="flex items-stretch gap-2 overflow-x-auto pb-2"
          data-testid="activity-trace-a2"
          role="list"
          aria-label="TRACE timeline"
        >
          {stages.map((stage, index) => {
            const tone = grammarToneForStepStatus(stage.status)
            const selected = active?.id === stage.id
            return (
              <div key={stage.id} className="flex items-center gap-2" role="listitem">
                <button
                  type="button"
                  onClick={() => setActiveId(stage.id)}
                  className={cn(
                    "min-w-[7.5rem] rounded-[var(--np-radius-md)] border px-3 py-2 text-left transition-colors",
                    selected
                      ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-soft)]/50"
                      : "border-divide bg-[color:var(--g-surface-2)] hover:bg-[color:var(--g-surface-1)]",
                    tone === "failed" && "border-destructive/40",
                    tone === "waiting" && "border-warning/40",
                  )}
                >
                  <span className="block text-xs font-semibold text-muted-foreground">
                    {stage.label}
                  </span>
                  <span className="mt-0.5 block text-xs font-medium text-foreground line-clamp-2">
                    {stage.summary || stage.status}
                  </span>
                </button>
                {index < stages.length - 1 ? (
                  <div className="h-px w-3 shrink-0 bg-[color:var(--g-border-default)]" aria-hidden />
                ) : null}
              </div>
            )
          })}
        </div>
      ) : (
        <div className="flex gap-3" data-testid="activity-trace-rail">
          <ol className="w-[7.5rem] shrink-0 space-y-0" aria-label="TRACE rail">
            {stages.map((stage, index) => {
              const tone = grammarToneForStepStatus(stage.status)
              const selected = active?.id === stage.id
              return (
                <li key={stage.id} className="relative">
                  <button
                    type="button"
                    onClick={() => setActiveId(stage.id)}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-md px-1.5 py-1.5 text-left",
                      selected ? "bg-[color:var(--g-surface-active)]" : "hover:bg-[color:var(--g-surface-2)]",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full border",
                        tone === "verified" || tone === "running"
                          ? "border-[color:var(--g-emerald)] bg-[color:var(--g-emerald)]"
                          : tone === "failed"
                            ? "border-destructive bg-destructive"
                            : tone === "waiting"
                              ? "border-warning bg-warning"
                              : "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]",
                      )}
                      aria-hidden
                    />
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-muted-foreground">
                        {stage.label}
                      </span>
                    </span>
                  </button>
                  {index < stages.length - 1 ? (
                    <span
                      className="absolute left-[0.7rem] top-7 h-[calc(100%-0.5rem)] w-px bg-[color:var(--g-border-subtle)]"
                      aria-hidden
                    />
                  ) : null}
                </li>
              )
            })}
          </ol>

          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={active?.id || "none"}
              initial={reduceMotion ? false : { opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -4 }}
              transition={{ duration: 0.18 }}
              className="min-w-0 flex-1 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-3"
              data-testid="activity-trace-story"
            >
              {active ? (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className={cn(TYPE.cardTitle, "text-sm")}>{active.label}</p>
                    {(() => {
                      const tone = grammarToneForStepStatus(active.status)
                      if (tone === "waiting") return <EvidenceChip label="Needs approval" tone="waiting" />
                      if (tone === "verified") return <EvidenceChip label="Verified" tone="evidence" />
                      if (tone === "failed") return <EvidenceChip label="Failed" tone="error" />
                      return (
                        <span className="rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {active.status}
                        </span>
                      )
                    })()}
                  </div>
                  {active.agentName ? (
                    <p className={cn(TYPE.meta, "mt-1")}>Actor · {active.agentName}</p>
                  ) : null}
                  <p className={cn(TYPE.bodyMuted, "mt-2 text-sm")}>
                    {active.summary || "No summary recorded for this stage."}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {(active.evidenceLabels || []).map((label) => (
                      <EvidenceChip key={label} label={label} tone="evidence" />
                    ))}
                    {active.evidenceUrl ? (
                      <a
                        href={active.evidenceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-medium text-[color:var(--g-brand)] hover:underline"
                      >
                        Open evidence
                      </a>
                    ) : null}
                  </div>
                  <div className="mt-4 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-canvas)] p-3">
                    <p className={TYPE.eyebrow}>Contextual AI</p>
                    <p className={cn(TYPE.meta, "mt-1")}>
                      {grammarToneForStepStatus(active.status) === "failed"
                        ? "Ask why this stage failed with outcome context attached."
                        : "Summarize this outcome or explain the selected stage."}
                    </p>
                    <AskGravitreSummonButton
                      className="mt-2 h-8 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] px-3 hover:no-underline"
                      selected={{
                        kind: "outcome",
                        id: outcome.id || outcome.runId || "",
                        label: outcome.title?.trim() || "Outcome",
                      }}
                    />
                  </div>
                </>
              ) : (
                <p className={TYPE.bodyMuted}>Select a TRACE stage.</p>
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      )}

      {active && view === "timeline" ? (
        <div className="rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-3">
          <p className={TYPE.eyebrow}>Selected stage</p>
          <p className={cn(TYPE.cardTitle, "mt-1 text-sm")}>{active.label}</p>
          <p className={cn(TYPE.bodyMuted, "mt-1 text-sm")}>{active.summary || active.status}</p>
        </div>
      ) : null}
    </div>
  )
}
