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

export const DEMO_ASSIGNMENTS: DemoAssignment[] = [
  {
    id: "assign-001",
    title: "Q3 Healthcare Campaign",
    brief: "Create multi-channel campaign targeting healthcare decision makers",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "running",
    progress: 67,
    steps: [
      { name: "Research", status: "done" },
      { name: "Strategy", status: "done" },
      { name: "Content", status: "running" },
      { name: "Review", status: "pending" },
    ],
    createdAt: "2 hours ago",
    outputTypes: ["Emails", "Social Posts", "Segments"],
    destination: "HubSpot + Outlook",
    currentStepDetail: "Fetching campaign data from HubSpot…",
  },
  {
    id: "assign-002",
    title: "Weekly Performance Report",
    brief: "Generate comprehensive weekly marketing performance analysis",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "needs_approval",
    progress: 100,
    steps: [
      { name: "Data Pull", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "done" },
      { name: "Approval", status: "running" },
    ],
    createdAt: "5 hours ago",
    completedAt: "4 hours ago",
    outputTypes: ["Report"],
    destination: "Slack",
    confidence: 94,
    reportContent: `Weekly Performance Report — Marketing

Overview
Pipeline influenced by marketing increased 12% week-over-week. Email and paid social remained the top contributors.

Highlights
• 847 MQLs generated (+8% vs prior week)
• HubSpot campaigns: 94% delivery rate, 31% open rate
• Slack digest ready for #marketing-leadership

Sections included
Executive summary, channel breakdown, top campaigns, and recommended next actions.

Note for reviewer
Q3 vs Q2 comparison chart is still being refreshed from CRM — all other sections are complete.`,
    qualityChecks: [
      { label: "All requested sections included", status: "pass" },
      { label: "Data sourced from HubSpot + CRM", status: "pass" },
      { label: "Format matches template", status: "pass" },
      { label: "Missing: Q3 vs Q2 comparison", status: "warn" },
    ],
  },
  {
    id: "assign-003",
    title: "Lead Scoring Analysis",
    brief: "Analyze and score all leads from Q2 campaign activities",
    agent: { name: "Nexus", role: "Sales Assistant", gradient: "from-blue-500 to-indigo-500", icon: TrendingUp },
    status: "completed",
    progress: 100,
    steps: [
      { name: "Import", status: "done" },
      { name: "Score", status: "done" },
      { name: "Segment", status: "done" },
      { name: "Export", status: "done" },
    ],
    createdAt: "1 day ago",
    completedAt: "1 day ago",
    outputTypes: ["Report", "Segments"],
    destination: "Salesforce",
    confidence: 98,
  },
  {
    id: "assign-004",
    title: "Email Sequence - Re-engagement",
    brief: "Design 5-email re-engagement sequence for dormant leads",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "pending",
    progress: 0,
    steps: [
      { name: "Research", status: "pending" },
      { name: "Draft", status: "pending" },
      { name: "Review", status: "pending" },
      { name: "Publish", status: "pending" },
    ],
    createdAt: "Just now",
    outputTypes: ["Emails"],
    destination: "HubSpot",
  },
  {
    id: "assign-005",
    title: "Competitor Analysis Report",
    brief: "Deep dive analysis of top 5 competitors market positioning",
    agent: { name: "Oracle", role: "Finance Reporter", gradient: "from-violet-500 to-purple-500", icon: PieChart },
    status: "failed",
    progress: 45,
    steps: [
      { name: "Research", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "pending" },
      { name: "Export", status: "pending" },
    ],
    createdAt: "2 days ago",
    outputTypes: ["Report"],
    destination: "Export",
  },
]

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

export function getDemoAssignment(id: string): DemoAssignment | undefined {
  return runtimeDemoAssignments.get(id) ?? DEMO_ASSIGNMENTS.find((item) => item.id === id)
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

function isDemoAssignmentId(id: string): boolean {
  return id.startsWith("assign-") || Boolean(getDemoAssignment(id))
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
  try {
    const response = await apiFetch(`/api/assignments/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: notes ?? "" }),
    })
    if (response.ok) {
      return response.json() as Promise<AgentJob>
    }
    if (response.status === 404 || response.status === 409) {
      if (isDemoAssignmentId(id)) {
        demoApprovalOverrides.set(id, { status: "approved", at: new Date().toISOString() })
        const demo = getDemoAssignment(id)
        if (demo) return demoAssignmentToAgentJob({ ...demo, status: "completed" })
      }
    }
    throw new Error(await parseApiError(response))
  } catch (err) {
    if (isDemoAssignmentId(id)) {
      demoApprovalOverrides.set(id, { status: "approved", at: new Date().toISOString() })
      const demo = getDemoAssignment(id)
      if (demo) return demoAssignmentToAgentJob({ ...demo, status: "completed" })
    }
    throw err instanceof Error ? err : new Error("Failed to approve assignment")
  }
}

export async function rejectAssignment(id: string, reason: string): Promise<AgentJob> {
  const trimmed = reason.trim()
  if (!trimmed) {
    throw new Error("A rejection reason is required")
  }
  try {
    const response = await apiFetch(`/api/assignments/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: trimmed }),
    })
    if (response.ok) {
      return response.json() as Promise<AgentJob>
    }
    if (response.status === 404 || response.status === 409) {
      if (isDemoAssignmentId(id)) {
        demoApprovalOverrides.set(id, { status: "rejected", reason: trimmed, at: new Date().toISOString() })
        const demo = getDemoAssignment(id)
        if (demo) {
          return {
            ...demoAssignmentToAgentJob({ ...demo, status: "failed" }),
            status: "cancelled",
            error: trimmed,
          }
        }
      }
    }
    throw new Error(await parseApiError(response))
  } catch (err) {
    if (isDemoAssignmentId(id)) {
      demoApprovalOverrides.set(id, { status: "rejected", reason: trimmed, at: new Date().toISOString() })
      const demo = getDemoAssignment(id)
      if (demo) {
        return {
          ...demoAssignmentToAgentJob({ ...demo, status: "failed" }),
          status: "cancelled",
          error: trimmed,
        }
      }
    }
    throw err instanceof Error ? err : new Error("Failed to reject assignment")
  }
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
  if (isDemoAssignmentId(id)) {
    const demo = getDemoAssignment(id)
    if (demo) {
      return demoAssignmentToAgentJob(demo)
    }
  }

  try {
    const response = await apiFetch(`/api/agent-jobs/${id}`)
    if (response.ok) {
      return response.json() as Promise<AgentJob>
    }
  } catch {
    // fall through to demo data
  }

  const demo = getDemoAssignment(id)
  if (demo) {
    return demoAssignmentToAgentJob(demo)
  }

  throw new Error("Assignment not found")
}
