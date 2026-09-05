"use client"

/**
 * Agent Elements–inspired SubagentTool group (ADAPT).
 * Nested specialist chrome for multi-agent subtasks — same list, quieter header.
 */

import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { Users } from "lucide-react"

export function SubagentToolGroup({
  count,
  children,
  className,
}: {
  count: number
  children: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn("overflow-hidden border bg-card", RADIUS.card, className)}
      data-testid="subagent-tool-group"
    >
      <div
        className={cn(
          "flex h-8 items-center gap-1.5 border-b border-border px-3",
          STATUS.running,
          "rounded-none border-x-0 border-t-0",
        )}
      >
        <Users className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className={cn(TYPE.meta, "font-medium")}>
          Agent contributions ({count})
        </span>
      </div>
      <div className="space-y-2 bg-background p-3">{children}</div>
    </div>
  )
}
