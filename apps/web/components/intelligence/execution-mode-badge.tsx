"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  readExecutionModeFields,
  type ExecutionModeFields,
  type IntelligenceExecutionMode,
} from "@/lib/execution-mode"

const MODE_STYLES: Record<IntelligenceExecutionMode, string> = {
  tools_executed: "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  advisory_only: "border-sky-500/40 bg-sky-500/10 text-sky-900 dark:text-sky-200",
  degraded: "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200",
}

export function ExecutionModeBadge({
  source,
  className,
  compact = false,
  showMeta = false,
}: {
  source: ExecutionModeFields | null | undefined
  className?: string
  compact?: boolean
  showMeta?: boolean
}) {
  const { mode, label, toolsAvailable, toolCallCount } = readExecutionModeFields(source)
  if (!mode || !label) return null

  const metaParts: string[] = []
  if (showMeta && typeof toolCallCount === "number") {
    metaParts.push(`${toolCallCount} tool call${toolCallCount === 1 ? "" : "s"}`)
  }
  if (showMeta && typeof toolsAvailable === "number") {
    metaParts.push(`${toolsAvailable} available`)
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        "font-normal",
        MODE_STYLES[mode],
        compact ? "text-[10px] px-1.5 py-0" : "text-xs",
        className,
      )}
      title={metaParts.length ? metaParts.join(" · ") : label}
    >
      {label}
      {showMeta && metaParts.length ? ` · ${metaParts.join(" · ")}` : null}
    </Badge>
  )
}
