import type { AgentJob, JobStatus } from "@/hooks/use-async-job"

export interface AgentJobHandoffResult {
  agent_id?: string
  agent_name?: string
  task?: { description?: string; status?: string }
  summary?: string
  answer?: string
  finding_description?: string
  status?: string
  react_status?: string
  recommended_actions?: string[]
  confidence?: number
  tool_calls?: Array<{ tool?: string; result?: { success?: boolean } }>
  react_trace?: Array<{ iteration?: number; thought?: string; action?: string; observation?: string }>
  rag_sources?: Array<{ source?: string; content?: string; score?: number }>
  error?: string
  needs_human_input?: boolean
  human_input_prompt?: string
  requires_approval?: boolean
  approval_status?: "approved" | "rejected"
  rejection_reason?: string
  approval_notes?: string
  action_title?: string
  action_description?: string
  progress_percent?: number
  aiStatus?: string
  persona?: string
  model?: string
  provider?: string
}

export interface ExecutionStepView {
  id: string
  name: string
  status: "completed" | "running" | "pending" | "error"
  duration?: string
  details?: string
}

export interface DeliverableView {
  id: string
  title: string
  type: "email" | "social" | "report" | "segment" | "workflow"
  status: "ready" | "pending" | "error"
  confidence: number
  preview: string
  sourceRefs: string[]
}

export function parseHandoffResult(job: AgentJob | null): AgentJobHandoffResult | null {
  if (!job?.result || typeof job.result !== "object") return null
  return job.result as AgentJobHandoffResult
}

export function jobProgress(status: JobStatus, result: AgentJobHandoffResult | null): number {
  if (typeof result?.progress_percent === "number") {
    return Math.max(0, Math.min(100, result.progress_percent))
  }
  if (status === "completed") return 100
  if (status === "failed" || status === "cancelled") return 100
  if (status === "paused") return 55
  if (status === "running") {
    const traceLen = result?.react_trace?.length ?? 0
    return Math.min(85, 35 + traceLen * 12)
  }
  if (status === "queued") return 12
  return 0
}

export function buildExecutionSteps(
  job: AgentJob,
  result: AgentJobHandoffResult | null,
): ExecutionStepView[] {
  const trace = result?.react_trace ?? []
  if (trace.length > 0) {
    return trace.map((step, index) => {
      const isLast = index === trace.length - 1
      const terminal = job.status === "completed" || job.status === "failed"
      let stepStatus: ExecutionStepView["status"] = "completed"
      if (terminal && isLast && job.status === "completed") stepStatus = "completed"
      else if (terminal && isLast && job.status === "failed") stepStatus = "error"
      else if (isLast && (job.status === "running" || job.status === "queued")) stepStatus = "running"
      else if (!isLast) stepStatus = "completed"

      const label = step.action ? `Tool: ${step.action}` : "Reasoning"
      const details = step.thought || step.observation || undefined
      return {
        id: `trace-${index}`,
        name: label,
        status: stepStatus,
        details,
      }
    })
  }

  const steps: ExecutionStepView[] = [
    { id: "plan", name: "Planning", status: "pending", details: "Analyzing task requirements" },
    { id: "context", name: "Gathering Context", status: "pending", details: "Loading org context and knowledge" },
    { id: "react", name: "Agent Execution", status: "pending", details: "Running tools and reasoning" },
    { id: "finalize", name: "Finalizing", status: "pending", details: "Preparing handoff result" },
  ]

  const statusIndex: Record<JobStatus, number> = {
    queued: 0,
    running: 2,
    paused: 2,
    completed: 4,
    failed: 3,
    cancelled: 3,
  }
  const active = statusIndex[job.status] ?? 0

  return steps.map((step, index) => {
    if (index < active) return { ...step, status: "completed" as const }
    if (index === active && (job.status === "running" || job.status === "queued" || job.status === "paused")) {
      return { ...step, status: "running" as const }
    }
    if (job.status === "failed" && index === active) return { ...step, status: "error" as const }
    if (job.status === "completed") return { ...step, status: "completed" as const }
    return step
  })
}

export function buildDeliverables(result: AgentJobHandoffResult | null): DeliverableView[] {
  if (!result) return []

  const items: DeliverableView[] = []
  const confidence = result.confidence ?? 0
  const sources = (result.rag_sources ?? [])
    .map((s) => s.source)
    .filter((s): s is string => Boolean(s))

  const answer = (result.answer || result.summary || "").trim()
  if (answer) {
    items.push({
      id: "primary-answer",
      title: "Agent Response",
      type: "report",
      status: "ready",
      confidence,
      preview: answer,
      sourceRefs: sources.slice(0, 4),
    })
  }

  for (const [index, action] of (result.recommended_actions ?? []).entries()) {
    items.push({
      id: `action-${index}`,
      title: action.length > 48 ? `${action.slice(0, 45)}…` : action,
      type: "workflow",
      status: "ready",
      confidence: Math.max(0, confidence - index * 3),
      preview: action,
      sourceRefs: sources.slice(0, 2),
    })
  }

  if (result.needs_human_input && result.human_input_prompt) {
    items.push({
      id: "clarification",
      title: "Clarification Needed",
      type: "report",
      status: "pending",
      confidence: 0,
      preview: result.human_input_prompt,
      sourceRefs: [],
    })
  }

  return items
}

export function formatJobStatus(status: JobStatus): string {
  return status.replace(/_/g, " ")
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "just now"
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return "just now"
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return new Date(iso).toLocaleDateString()
}
