/** Phase 5 — research plan visualization for adaptive cascade stages. */
"use client"

import { CheckCircle2, Circle, MinusCircle, SkipForward } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  deriveNamedProgressSteps,
  formatStepCounter,
  type PendingTaskLike,
} from "@/lib/chat-progress-steps"
import { ProgressChecklist } from "@/components/gravitre/assistant/progress-checklist"
import type { CascadeStageProgress, ResearchCascadePayload } from "./research-cascade-types"

type ResearchPlanPanelProps = {
  cascade: ResearchCascadePayload | null | undefined
  progressSteps?: string[] | null
  pendingTask?: PendingTaskLike
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
  pendingTask,
  strategicPlan,
  className,
}: ResearchPlanPanelProps) {
  const stages = cascade?.stage_progress ?? []
  const steps = progressSteps?.length ? progressSteps : cascade?.progress_steps ?? []
  const scope = cascade?.research_scope?.replace(/_/g, " ")
  const namedSteps = deriveNamedProgressSteps(steps, pendingTask)
  const stepCounter = formatStepCounter(namedSteps)
  const showNamedSteps = namedSteps.length >= 2
  const panelTitle = namedSteps.length >= 2 ? "Progress" : "Research plan"

  if (!stages.length && !showNamedSteps && !strategicPlan?.goal) return null

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

      {showNamedSteps ? (
        <div className={cn(stages.length > 0 || strategicPlan?.goal ? "mt-2.5 border-t border-border/40 pt-2.5" : "mt-2")}>
          <ProgressChecklist steps={namedSteps} />
        </div>
      ) : null}
    </div>
  )
}
