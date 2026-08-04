/** Phase 5 — research plan visualization for adaptive cascade stages. */
"use client"

import { CheckCircle2, Circle, Loader2, MinusCircle, SkipForward } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  deriveNamedProgressSteps,
  formatStepCounter,
  isActionProgressStep,
} from "@/lib/chat-progress-steps"
import type { CascadeStageProgress, ResearchCascadePayload } from "./research-cascade-types"

type ResearchPlanPanelProps = {
  cascade: ResearchCascadePayload | null | undefined
  progressSteps?: string[] | null
  strategicPlan?: {
    goal?: string
    confidence?: number
    risks?: Array<{ title?: string; summary?: string; severity?: string }>
  } | null
  className?: string
}

function StageIcon({ status }: { status: CascadeStageProgress["status"] }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
    case "empty":
      return <MinusCircle className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
    case "skipped":
      return <SkipForward className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
    default:
      return <Circle className="h-3.5 w-3.5 text-primary" aria-hidden />
  }
}

export function ResearchPlanPanel({
  cascade,
  progressSteps,
  strategicPlan,
  className,
}: ResearchPlanPanelProps) {
  const stages = cascade?.stage_progress ?? []
  const steps = progressSteps?.length ? progressSteps : cascade?.progress_steps ?? []
  const scope = cascade?.research_scope?.replace(/_/g, " ")
  const actionSteps = steps.filter(isActionProgressStep)
  // Shared derivation so a step reads identically here and in TaskSidePanel.
  const namedSteps = deriveNamedProgressSteps(steps, null)
  const stepCounter = formatStepCounter(namedSteps)
  const panelTitle = actionSteps.length > 0 ? "Progress" : "Research plan"

  if (!stages.length && !steps.length && !strategicPlan?.goal) return null

  return (
    <div
      className={cn(
        "rounded-xl border border-border/60 bg-card/40 px-4 py-3 text-sm",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">{panelTitle}</p>
        <div className="flex flex-wrap items-center gap-2">
          {stepCounter ? (
            <span className="text-[11px] font-medium text-foreground">{stepCounter}</span>
          ) : null}
          {scope ? <span className="text-[11px] capitalize text-muted-foreground">Scope: {scope}</span> : null}
        </div>
      </div>

      {strategicPlan?.goal ? (
        <p className="mt-2 text-xs text-foreground">{strategicPlan.goal}</p>
      ) : null}

      {stages.length > 0 ? (
        <ol className="mt-3 space-y-1.5">
          {stages.map((stage) => (
            <li key={stage.stage} className="flex items-start gap-2 text-xs">
              <StageIcon status={stage.status} />
              <div className="min-w-0">
                <span className="text-foreground">{stage.label}</span>
                {stage.detail ? (
                  <span className="text-muted-foreground"> — {stage.detail}</span>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      {/* Named action pills. Labels come from the shared parser, so the raw
          "Running: " / "Completed: " SSE prefixes never reach the user. */}
      {namedSteps.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1.5 border-t border-border/40 pt-2.5">
          {namedSteps.slice(0, 8).map((step, index) => (
            <li
              key={`${step.label}-${index}`}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px]",
                step.status === "current" &&
                  "border-emerald-500/30 bg-emerald-500/5 font-medium text-foreground",
                step.status === "done" && "border-border/50 bg-background/60 text-muted-foreground",
                step.status === "pending" &&
                  "border-dashed border-border/50 text-muted-foreground/70",
              )}
            >
              {step.status === "done" ? (
                <CheckCircle2
                  className="h-3 w-3 shrink-0 text-emerald-600 dark:text-emerald-400"
                  aria-hidden
                />
              ) : step.status === "current" ? (
                <Loader2
                  className="h-3 w-3 shrink-0 animate-spin text-emerald-600 dark:text-emerald-400"
                  aria-hidden
                />
              ) : (
                <Circle className="h-2.5 w-2.5 shrink-0 text-muted-foreground/50" aria-hidden />
              )}
              <span className="truncate">{step.label}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
