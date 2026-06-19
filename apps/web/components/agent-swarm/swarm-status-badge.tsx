"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { AgentSwarmRunStatus, AgentSwarmSubtaskStatus } from "@/types/api"

const RUN_STATUS: Record<
  AgentSwarmRunStatus,
  { label: string; className: string }
> = {
  pending: { label: "Pending", className: "border-muted-foreground/30 bg-muted/40 text-muted-foreground" },
  running: { label: "Running", className: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  aggregating: { label: "Aggregating", className: "border-violet-500/30 bg-violet-500/10 text-violet-600 dark:text-violet-400" },
  completed: { label: "Completed", className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  failed: { label: "Failed", className: "border-destructive/30 bg-destructive/10 text-destructive" },
  cancelled: { label: "Cancelled", className: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400" },
}

const SUBTASK_STATUS: Record<
  AgentSwarmSubtaskStatus,
  { label: string; className: string }
> = {
  queued: { label: "Queued", className: "border-muted-foreground/30 bg-muted/40 text-muted-foreground" },
  running: { label: "Running", className: "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  completed: { label: "Done", className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" },
  failed: { label: "Failed", className: "border-destructive/30 bg-destructive/10 text-destructive" },
  cancelled: { label: "Cancelled", className: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400" },
}

export function SwarmRunStatusBadge({ status }: { status: AgentSwarmRunStatus }) {
  const meta = RUN_STATUS[status] ?? RUN_STATUS.pending
  return (
    <Badge variant="outline" className={cn("font-normal", meta.className)}>
      {meta.label}
    </Badge>
  )
}

export function SwarmSubtaskStatusBadge({ status }: { status: AgentSwarmSubtaskStatus }) {
  const meta = SUBTASK_STATUS[status] ?? SUBTASK_STATUS.queued
  return (
    <Badge variant="outline" className={cn("font-normal text-xs", meta.className)}>
      {meta.label}
    </Badge>
  )
}
