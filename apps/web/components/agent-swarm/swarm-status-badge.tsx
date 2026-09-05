"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { STATUS } from "@/lib/design-system"
import type { AgentSwarmRunStatus, AgentSwarmSubtaskStatus } from "@/types/api"

const RUN_STATUS: Record<
  AgentSwarmRunStatus,
  { label: string; className: string }
> = {
  pending: { label: "Pending", className: STATUS.idle },
  running: { label: "Running", className: STATUS.running },
  aggregating: { label: "Aggregating", className: STATUS.running },
  completed: { label: "Completed", className: STATUS.verified },
  failed: { label: "Failed", className: STATUS.failed },
  cancelled: { label: "Cancelled", className: STATUS.pending },
}

const SUBTASK_STATUS: Record<
  AgentSwarmSubtaskStatus,
  { label: string; className: string }
> = {
  queued: { label: "Queued", className: STATUS.idle },
  running: { label: "Running", className: STATUS.running },
  completed: { label: "Done", className: STATUS.verified },
  failed: { label: "Failed", className: STATUS.failed },
  cancelled: { label: "Cancelled", className: STATUS.pending },
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
