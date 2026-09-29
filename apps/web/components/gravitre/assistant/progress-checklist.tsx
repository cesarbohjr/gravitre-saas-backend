"use client"

import { GravitreTaskRow, type TaskRowState } from "@/components/gravitre/ai-native"
import { cn } from "@/lib/utils"
import type { NamedProgressStep } from "@/lib/chat-progress-steps"

const STEP_STATE: Record<NamedProgressStep["status"], TaskRowState> = {
  done: "done",
  current: "running",
  pending: "pending",
}

export function ProgressChecklist({
  steps,
  className,
}: {
  steps: NamedProgressStep[]
  className?: string
}) {
  if (steps.length === 0) {
    return <p className="text-xs text-muted-foreground">No steps yet for this task.</p>
  }

  return (
    <ol className={cn("min-w-0", className)} data-testid="progress-checklist" aria-label="Task checklist">
      {steps.map((step, index) => (
        <GravitreTaskRow
          key={`${step.label}-${index}`}
          state={STEP_STATE[step.status] ?? "pending"}
          title={step.label}
          className="py-1.5"
        />
      ))}
    </ol>
  )
}
