import type { AgentJob } from "@/hooks/use-async-job"
import { apiFetch } from "@/lib/fetcher"
import {
  type DemoAssignment,
  inferAgentIconForRole,
} from "@/lib/demo-assignments"
const ASSIGNMENTS_REFRESH_KEY = "assignments-list"

export { ASSIGNMENTS_REFRESH_KEY }

function mapJobStatus(job: AgentJob): DemoAssignment["status"] {
  const result = job.result
  if (job.status === "queued") return "pending"
  if (job.status === "running") return "running"
  if (job.status === "failed" || job.status === "cancelled") return "failed"
  if (job.status === "completed") {
    if (result?.requires_approval || result?.needs_human_input) return "needs_approval"
    return "completed"
  }
  return "pending"
}

function mapJobToAssignment(job: AgentJob): DemoAssignment {
  const result = job.result
  const brief =
    result?.task?.description?.trim() ||
    result?.finding_description?.trim() ||
    result?.summary?.trim() ||
    "Agent task"
  const title = result?.action_title?.trim() || brief.slice(0, 72)
  const agentName = result?.agent_name?.trim() || "Agent"
  const progressPercent = result?.progress_percent

  return {
    id: job.jobId,
    title,
    brief,
    agent: {
      name: agentName,
      role: "AI Agent",
      gradient: "from-emerald-500 to-teal-500",
      icon: inferAgentIconForRole(agentName),
    },
    status: mapJobStatus(job),
    progress:
      job.status === "completed" || job.status === "failed"
        ? mapJobStatus(job) === "failed"
          ? Math.max(10, Math.round((progressPercent ?? 0.45) * 100))
          : 100
        : job.status === "running"
          ? Math.max(5, Math.round((progressPercent ?? 0.35) * 100))
          : 0,
    steps: [
      {
        name: "Execute",
        status:
          job.status === "running"
            ? "running"
            : job.status === "completed"
              ? "done"
              : "pending",
      },
      { name: "Deliver", status: job.status === "completed" ? "done" : "pending" },
    ],
    createdAt: "Recently",
    outputTypes: ["Task"],
    destination: "Review",
    confidence: result?.confidence ? Math.round(result.confidence * 100) : undefined,
  }
}

export async function fetchAssignmentList(): Promise<DemoAssignment[]> {
  try {
    const response = await apiFetch("/api/assignments?limit=50")
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      const detail =
        payload && typeof payload === "object" && "detail" in payload
          ? String((payload as { detail?: unknown }).detail)
          : `Request failed (${response.status})`
      throw new Error(detail)
    }

    const payload = (await response.json()) as { jobs?: AgentJob[] }
    return (payload.jobs ?? []).map(mapJobToAssignment)
  } catch (error) {
    if (error instanceof Error) throw error
    throw new Error("Unable to load assignments")
  }
}
