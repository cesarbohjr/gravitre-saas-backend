/**
 * Agent runtime status — single source of truth for roster + profile chips.
 *
 * Backend enum: AgentStatus = active | idle | processing | error
 * (apps/web/types/api.ts). Do not invent TRAINED / healthy / Limited / Training
 * labels that are not this enum.
 *
 * Phase 4 presentation language:
 *   processing → Running (PULSE)
 *   active     → Active (static beacon)
 *   idle       → Idle
 *   error      → Failed
 *
 * Task/job row statuses may additionally show Needs input when the job payload
 * says so (paused / needs_human_input / awaiting_approval).
 */

import type { AgentStatus } from "@/types/api"
import { STATUS } from "@/lib/design-system"

export type AgentRuntimePresentation = {
  /** API status (unchanged). */
  status: AgentStatus
  /** User-facing chip label. */
  label: string
  /** Tailwind text color utility. */
  color: string
  /** Tailwind dot fill utility. */
  dotColor: string
  /** Border/bg chip utilities. */
  chipClass: string
  /** Continuous motion allowed only while work is in flight. */
  pulse: boolean
  /** StatusBeacon status key. */
  beacon: "active" | "idle" | "processing" | "error"
}

const CONFIG: Record<AgentStatus, Omit<AgentRuntimePresentation, "status">> = {
  active: {
    label: "Active",
    color: "text-[color:var(--status-verified)]",
    dotColor: "bg-[color:var(--status-verified)]",
    chipClass: STATUS.verified,
    pulse: false,
    beacon: "active",
  },
  idle: {
    label: "Idle",
    color: "text-muted-foreground",
    dotColor: "bg-muted-foreground",
    chipClass: STATUS.idle,
    pulse: false,
    beacon: "idle",
  },
  processing: {
    label: "Running",
    color: "text-[color:var(--status-running)]",
    dotColor: "bg-[color:var(--status-running)]",
    chipClass: STATUS.running,
    pulse: true,
    beacon: "processing",
  },
  error: {
    label: "Failed",
    color: "text-[color:var(--status-failed)]",
    dotColor: "bg-[color:var(--status-failed)]",
    chipClass: STATUS.failed,
    pulse: false,
    beacon: "error",
  },
}

export function normalizeAgentStatus(raw: unknown): AgentStatus {
  const status = String(raw ?? "idle")
  if (status === "active" || status === "processing" || status === "error") return status
  return "idle"
}

export function presentAgentStatus(status: AgentStatus): AgentRuntimePresentation {
  return { status, ...CONFIG[status] }
}

/** Task / job row badge classes — includes Needs input for paused/awaiting paths. */
export function taskRuntimeBadgeClass(status: string): string {
  const key = status.trim().toLowerCase()
  switch (key) {
    case "completed":
      return STATUS.verified
    case "running":
    case "processing":
    case "queued":
      return STATUS.running
    case "failed":
    case "error":
    case "cancelled":
      return STATUS.failed
    case "paused":
    case "needs_input":
    case "needs_human_input":
    case "awaiting_approval":
    case "pending_approval":
      return STATUS.pending
    default:
      return STATUS.idle
  }
}

export function taskRuntimeLabel(status: string): string {
  const key = status.trim().toLowerCase()
  switch (key) {
    case "running":
    case "processing":
      return "Running"
    case "queued":
      return "Queued"
    case "completed":
      return "Completed"
    case "failed":
    case "error":
      return "Failed"
    case "cancelled":
      return "Cancelled"
    case "paused":
    case "needs_input":
    case "needs_human_input":
      return "Needs input"
    case "awaiting_approval":
    case "pending_approval":
      return "Pending approval"
    default:
      return status || "Unknown"
  }
}

export function agentStatusIsLiveWork(status: AgentStatus): boolean {
  return status === "processing"
}
