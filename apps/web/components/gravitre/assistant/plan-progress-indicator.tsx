"use client"

import { useState } from "react"
import { CheckCircle2, ChevronDown, Circle } from "lucide-react"
import { cn } from "@/lib/utils"

type PlanStep = {
  step_id?: string
  description?: string
}

type TaskState = {
  current_plan?: { steps?: PlanStep[] } | null
  completed_steps?: PlanStep[]
  pending_steps?: PlanStep[]
}

export function PlanProgressIndicator({ taskState }: { taskState: TaskState | null | undefined }) {
  const [expanded, setExpanded] = useState(false)
  if (!taskState?.current_plan?.steps?.length) return null

  const steps = taskState.current_plan.steps
  const completedIds = new Set(
    (taskState.completed_steps ?? []).map((step) => step.step_id).filter(Boolean),
  )
  const completedCount = steps.filter((step) => step.step_id && completedIds.has(step.step_id)).length
  const currentStep =
    (taskState.pending_steps ?? [])[0] ??
    steps.find((step) => step.step_id && !completedIds.has(step.step_id))

  return (
    <div className="border-b border-zinc-200 bg-white px-4 py-2 md:px-6 dark:border-zinc-800 dark:bg-zinc-950">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between text-left"
      >
        <div>
          <p className="text-xs font-medium text-zinc-700 dark:text-zinc-200">Active plan</p>
          <p className="text-[11px] text-zinc-500">
            Step {Math.min(completedCount + 1, steps.length)} of {steps.length}
            {currentStep?.description ? ` — ${currentStep.description}` : ""}
          </p>
        </div>
        <ChevronDown className={cn("h-4 w-4 text-zinc-400 transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded ? (
        <ul className="mt-2 space-y-1.5">
          {steps.map((step) => {
            const done = step.step_id ? completedIds.has(step.step_id) : false
            return (
              <li key={step.step_id ?? step.description} className="flex items-start gap-2 text-xs text-zinc-600">
                {done ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
                ) : (
                  <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-zinc-300" />
                )}
                <span className={cn(done && "text-zinc-400 line-through")}>{step.description}</span>
              </li>
            )
          })}
        </ul>
      ) : null}
    </div>
  )
}
