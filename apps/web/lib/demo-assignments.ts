import type { LucideIcon } from "lucide-react"
import {
  Megaphone,
  TrendingUp,
  PieChart,
  Database,
  Headphones,
  Brain,
} from "lucide-react"
import { apiFetch } from "@/lib/fetcher"
import type { AgentJob, JobStatus } from "@/hooks/use-async-job"

export interface DemoAssignment {
  id: string
  title: string
  brief: string
  agent: { name: string; role: string; gradient: string; icon: LucideIcon }
  status: "running" | "completed" | "pending" | "failed" | "needs_approval"
  progress: number
  steps: { name: string; status: "done" | "running" | "pending" }[]
  createdAt: string
  completedAt?: string
  outputTypes: string[]
  destination: string
  confidence?: number
  currentStepDetail?: string
  reportContent?: string
  qualityChecks?: Array<{ label: string; status: "pass" | "warn" }>
}

const runtimeDemoAssignments = new Map<string, DemoAssignment>()

export function registerDemoAssignment(assignment: DemoAssignment): void {
  runtimeDemoAssignments.set(assignment.id, assignment)
}

export function listRuntimeDemoAssignments(): DemoAssignment[] {
  return Array.from(runtimeDemoAssignments.values())
}

export function inferAgentIconForRole(role: string): LucideIcon {
  const normalized = role.toLowerCase()
  if (normalized.includes("marketing")) return Megaphone
  if (normalized.includes("sales")) return TrendingUp
  if (normalized.includes("data")) return Database
  if (normalized.includes("finance")) return PieChart
  if (normalized.includes("support")) return Headphones
  return Brain
}

/** Optimistic assignments created locally before the API responds. */
export function getLocalAssignment(id: string): DemoAssignment | undefined {
  return runtimeDemoAssignments.get(id)
}

export type DemoApprovalState = {
  status: "approved" | "rejected"
  reason?: string
  at: string
}

const demoApprovalOverrides = new Map<string, DemoApprovalState>()

export function getDemoApprovalState(id: string): DemoApprovalState | undefined {
  return demoApprovalOverrides.get(id)
}

async function parseApiError(response: Response): Promise<string> {
  const payload = await response.json().catch(() => ({}))
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return String(detail[0])
    }
  }
  return `Request failed (${response.status})`
}

export async function approveAssignment(id: string, notes?: string): Promise<AgentJob> {
  const response = await apiFetch(`/api/assignments/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notes: notes ?? "" }),
  })
  if (response.ok) {
    return response.json() as Promise<AgentJob>
  }
  throw new Error(await parseApiError(response))
}

export async function rejectAssignment(id: string, reason: string): Promise<AgentJob> {
  const trimmed = reason.trim()
  if (!trimmed) {
    throw new Error("A rejection reason is required")
  }
  const response = await apiFetch(`/api/assignments/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: trimmed }),
  })
  if (response.ok) {
    return response.json() as Promise<AgentJob>
  }
  throw new Error(await parseApiError(response))
}

function mapDemoStatus(status: DemoAssignment["status"]): JobStatus {
  if (status === "running") return "running"
  if (status === "completed") return "completed"
  if (status === "failed") return "failed"
  if (status === "needs_approval") return "completed"
  return "queued"
}

export function demoAssignmentToAgentJob(demo: DemoAssignment): AgentJob {
  const mappedStatus = mapDemoStatus(demo.status)
  const override = demoApprovalOverrides.get(demo.id)
  const requiresApproval = demo.status === "needs_approval" && override?.status !== "approved"
  const resultBase = {
    task: { description: demo.brief, status: override?.status === "approved" ? "completed" : demo.status },
    analysis_summary: demo.brief,
    finding_description: demo.brief,
    action_title: demo.title,
    action_description: `Deliverables: ${demo.outputTypes.join(", ")} → ${demo.destination}`,
    progress_percent: demo.progress,
    confidence: (demo.confidence ?? demo.progress) / 100,
    requires_approval: requiresApproval,
    agent_name: demo.agent.name,
    summary: demo.brief,
    answer: demo.reportContent ?? demo.brief,
    recommended_actions: demo.steps.map((step) => step.name),
    react_trace: demo.steps.map((step, index) => ({
      iteration: index + 1,
      thought: step.name,
      action:
        step.status === "done"
          ? "Completed"
          : step.status === "running"
            ? "Running"
            : "Pending",
      observation:
        step.status === "running" && demo.currentStepDetail
          ? demo.currentStepDetail
          : step.status === "done"
            ? `${step.name} completed`
            : undefined,
    })),
  }
  if (override?.status === "approved") {
    Object.assign(resultBase, {
      approval_status: "approved",
      requires_approval: false,
      approved_at: override.at,
    })
  }
  if (override?.status === "rejected") {
    Object.assign(resultBase, {
      approval_status: "rejected",
      requires_approval: false,
      rejection_reason: override.reason,
      rejected_at: override.at,
    })
  }
  return {
    jobId: demo.id,
    kind: "operator_task",
    status:
      override?.status === "rejected"
        ? "cancelled"
        : override?.status === "approved" || mappedStatus === "completed"
          ? "completed"
          : mappedStatus,
    sessionId: null,
    result: resultBase,
    error:
      override?.status === "rejected"
        ? override.reason ?? "Rejected by reviewer"
        : demo.status === "failed"
          ? "Task failed during report generation."
          : null,
    attempts: 1,
    createdAt: new Date().toISOString(),
    finishedAt:
      mappedStatus === "completed" || mappedStatus === "failed" || override
        ? new Date().toISOString()
        : null,
  }
}

export async function fetchAssignmentJob(id: string): Promise<AgentJob> {
  try {
    const response = await apiFetch(`/api/agent-jobs/${id}`)
    if (response.ok) {
      return response.json() as Promise<AgentJob>
    }
  } catch {
    // fall through to optimistic local assignment if present
  }

  const local = getLocalAssignment(id)
  if (local) {
    return demoAssignmentToAgentJob(local)
  }

  throw new Error("Assignment not found")
}
