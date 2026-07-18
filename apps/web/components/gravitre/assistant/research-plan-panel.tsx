"""Phase 5 — research plan visualization for adaptive cascade stages."""
"use client"

import { CheckCircle2, Circle, MinusCircle, SkipForward } from "lucide-react"
import { cn } from "@/lib/utils"
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

  if (!stages.length && !steps.length && !strategicPlan?.goal) return null

  return (
    <div
      className={cn(
        "rounded-xl border border-border/60 bg-card/40 px-4 py-3 text-sm",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">Research plan</p>
        {scope ? <span className="text-[11px] capitalize text-muted-foreground">Scope: {scope}</span> : null}
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

      {steps.length > 0 ? (
        <ul className="mt-2 space-y-1 border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
          {steps.slice(0, 6).map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
