"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/** Safe routing trace — never renders chain-of-thought or raw prompts. */
export function IntelligenceTrace({
  stages,
  className,
}: {
  stages: Array<{ label: string; detail?: string; status?: "ok" | "warn" | "pending" }>
  className?: string
}) {
  if (!stages.length) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        Trace will appear after the next intelligence request completes.
      </p>
    )
  }

  return (
    <ol className={cn("space-y-2", className)}>
      {stages.map((stage, index) => (
        <li
          key={`${stage.label}-${index}`}
          className="flex items-start gap-3 rounded-lg border border-border/60 bg-secondary/30 px-3 py-2"
        >
          <Badge variant="outline" className="mt-0.5 shrink-0 tabular-nums">
            {index + 1}
          </Badge>
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{stage.label}</p>
            {stage.detail ? (
              <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground text-pretty">
                {stage.detail}
              </p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  )
}
