"use client"

import { useState } from "react"
import { CheckCircle2, ChevronDown, Circle, AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

type PlanStep = {
  step_id?: string
  description?: string
}

type PlanRisk = {
  title?: string
  summary?: string
  severity?: string
}

type StrategicPlan = {
  goal?: string
  steps?: PlanStep[]
  risks?: PlanRisk[]
  confidence?: number
  approvals_required?: string[]
}

type TaskState = {
  current_plan?: StrategicPlan | null
  completed_steps?: PlanStep[]
  pending_steps?: PlanStep[]
}

export function PlanProgressIndicator({ taskState }: { taskState: TaskState | null | undefined }) {
  const [expanded, setExpanded] = useState(false)
  if (!taskState?.current_plan?.steps?.length) return null

  const plan = taskState.current_plan
  const steps = plan.steps ?? []
  const completedIds = new Set(
    (taskState.completed_steps ?? []).map((step) => step.step_id).filter(Boolean),
  )
  const completedCount = steps.filter((step) => step.step_id && completedIds.has(step.step_id)).length
  const currentStep =
    (taskState.pending_steps ?? [])[0] ??
    steps.find((step) => step.step_id && !completedIds.has(step.step_id))

  return (
    <div className="border-b border-border bg-card/40 px-4 py-2 md:px-6">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between text-left"
      >
        <div>
          <p className="text-xs font-medium text-foreground">Active plan</p>
          <p className="text-[11px] text-muted-foreground">
            Step {Math.min(completedCount + 1, steps.length)} of {steps.length}
            {currentStep?.description ? ` — ${currentStep.description}` : ""}
            {plan.confidence != null ? ` · ${Math.round(plan.confidence * 100)}% plan confidence` : ""}
          </p>
        </div>
        <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded ? (
        <div className="mt-2 space-y-3">
          {plan.goal ? <p className="text-xs text-muted-foreground">Goal: {plan.goal}</p> : null}
          <ul className="space-y-1.5">
            {steps.map((step) => {
              const done = step.step_id ? completedIds.has(step.step_id) : false
              return (
                <li key={step.step_id ?? step.description} className="flex items-start gap-2 text-xs text-muted-foreground">
                  {done ? (
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
                  )}
                  <span className={cn(done && "text-muted-foreground/70 line-through")}>{step.description}</span>
                </li>
              )
            })}
          </ul>
          {plan.risks?.length ? (
            <div>
              <p className="mb-1 text-[11px] font-medium text-foreground">Risks</p>
              <ul className="space-y-1">
                {plan.risks.slice(0, 4).map((risk) => (
                  <li key={risk.title ?? risk.summary} className="flex items-start gap-2 text-xs text-amber-800 dark:text-amber-300">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      <span className="font-medium">{risk.title}</span>
                      {risk.summary ? `: ${risk.summary}` : null}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
