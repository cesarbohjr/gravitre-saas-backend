"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

/** True when the API marks the run/subtask as not tool-verified (includes legacy rows without the field). */
export function isSwarmExecutionUnverified(executionVerified: boolean | undefined): boolean {
  return executionVerified !== true
}

export function SwarmVerificationLabel({
  className,
  compact = false,
}: {
  className?: string
  compact?: boolean
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "font-normal border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300",
        compact ? "text-[10px] px-1.5 py-0" : "text-xs",
        className,
      )}
    >
      Suggested — not verified
    </Badge>
  )
}
