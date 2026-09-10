"use client"

import { CheckCircle, Circle } from "@phosphor-icons/react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { NamedProgressStep } from "@/lib/chat-progress-steps"

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
    <ol className={cn("space-y-2", className)} data-testid="progress-checklist" aria-label="Task checklist">
      {steps.map((step, index) => (
        <li key={`${step.label}-${index}`} className="flex items-start gap-2 text-xs">
          <span className="mt-px flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden>
            {step.status === "done" ? (
              <CheckCircle
                className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400"
                weight="fill"
              />
            ) : step.status === "current" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-600 dark:text-emerald-400" />
            ) : (
              <Circle className="h-3 w-3 text-muted-foreground/50" weight="bold" />
            )}
          </span>
          <span
            className={cn(
              "min-w-0 leading-relaxed",
              step.status === "current" && "font-medium text-foreground",
              step.status === "done" && "text-muted-foreground",
              step.status === "pending" && "text-muted-foreground/70",
            )}
          >
            {step.label}
          </span>
          <span className="sr-only">
            {step.status === "done"
              ? "(completed)"
              : step.status === "current"
                ? "(in progress)"
                : "(pending)"}
          </span>
        </li>
      ))}
    </ol>
  )
}
