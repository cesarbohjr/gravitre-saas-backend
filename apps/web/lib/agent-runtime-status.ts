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
    color: "text-success",
    dotColor: "bg-success",
    chipClass: "border-success/40 bg-success/10 text-success",
    pulse: false,
    beacon: "active",
  },
  idle: {
    label: "Idle",
    color: "text-muted-foreground",
    dotColor: "bg-muted-foreground",
    chipClass: "border-border bg-muted text-muted-foreground",
    pulse: false,
    beacon: "idle",
  },
  processing: {
    label: "Running",
    color: "text-info",
    dotColor: "bg-info",
    chipClass: "border-info/30 bg-info/10 text-info",
    pulse: true,
    beacon: "processing",
  },
  error: {
    label: "Failed",
    color: "text-destructive",
    dotColor: "bg-destructive",
    chipClass: "border-destructive/40 bg-destructive/10 text-destructive",
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
      return "bg-success/10 text-success"
    case "running":
    case "processing":
    case "queued":
      return "bg-info/10 text-info"
    case "failed":
    case "error":
    case "cancelled":
      return "bg-destructive/10 text-destructive"
    case "paused":
    case "needs_input":
    case "needs_human_input":
    case "awaiting_approval":
    case "pending_approval":
      return "bg-warning/10 text-warning"
    default:
      return "bg-secondary text-muted-foreground"
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
