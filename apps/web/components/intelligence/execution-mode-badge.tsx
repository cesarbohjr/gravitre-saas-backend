"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  readExecutionModeFields,
  type ExecutionModeFields,
  type IntelligenceExecutionMode,
} from "@/lib/execution-mode"

/**
 * Execution mode is a health signal, so it maps onto the semantic tone tokens
 * rather than raw palette hues: tools actually ran (success), advisory-only
 * (informational), degraded (warning). These tokens already carry per-theme
 * values, so the old `dark:` overrides aren't needed.
 */
const MODE_STYLES: Record<IntelligenceExecutionMode, string> = {
  tools_executed: "border-success/40 bg-success/10 text-success",
  advisory_only: "border-info/40 bg-info/10 text-info",
  degraded: "border-warning/40 bg-warning/10 text-warning",
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
