import { apiFetch } from "@/lib/fetcher"
import type { AgentJob } from "@/hooks/use-async-job"
import {
  type DemoAssignment,
  inferAgentIconForRole,
  registerDemoAssignment,
} from "@/lib/demo-assignments"

export type AssignmentPriority = "low" | "normal" | "high" | "urgent"

export type CreateAssignmentInput = {
  agentId: string
  agentName: string
  agentRole: string
  agentGradient: string
  task: string
  priority: AssignmentPriority
  dueDate?: string
}

function avatarGradient(color?: string): string {
  const value = color || ""
  if (value.includes("blue")) return "from-blue-500 to-indigo-500"
  if (value.includes("amber")) return "from-amber-500 to-orange-500"
  if (value.includes("purple") || value.includes("violet")) return "from-violet-500 to-purple-500"
  if (value.includes("rose")) return "from-rose-500 to-pink-500"
  if (value.includes("cyan")) return "from-cyan-500 to-blue-500"
  return "from-emerald-500 to-teal-500"
}

export function buildQueuedAssignment(input: CreateAssignmentInput, id?: string): DemoAssignment {
  const trimmedTask = input.task.trim()
  const firstLine = trimmedTask.split("\n")[0]?.trim() ?? ""
  const title = firstLine.length > 72 ? `${firstLine.slice(0, 69)}…` : firstLine || "New assignment"

  return {
    id: id ?? `assign-${Date.now()}`,
    title,
    brief: trimmedTask,
    agent: {
      name: input.agentName,
      role: input.agentRole,
      gradient: input.agentGradient || avatarGradient(""),
      icon: inferAgentIconForRole(input.agentRole),
    },
    status: "pending",
    progress: 0,
    steps: [
      { name: "Queued", status: "running" },
      { name: "Execute", status: "pending" },
      { name: "Deliver", status: "pending" },
    ],
    createdAt: "Just now",
    outputTypes: ["Task"],
    destination: "Review",
  }
}

export async function createAssignment(
  input: CreateAssignmentInput,
): Promise<{ id: string; assignment: DemoAssignment }> {
  const response = await apiFetch("/api/assignments", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      task: input.task.trim(),
      agent_id: input.agentId,
      context: {
        priority: input.priority,
        due_date: input.dueDate || undefined,
      },
    }),
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    const message =
      payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail?: unknown }).detail ?? "")
        : `Assignment failed (${response.status})`
    throw new Error(message || "Assignment could not be created.")
  }

  const job = (await response.json()) as AgentJob
  if (!job?.jobId) {
    throw new Error("Assignment was accepted but no job id was returned.")
  }

  const assignment = buildQueuedAssignment(input, job.jobId)
  registerDemoAssignment(assignment)
  return { id: assignment.id, assignment }
}

export { avatarGradient }

async function jobActionError(response: Response, fallback: string): Promise<string> {
  const payload = await response.json().catch(() => ({}))
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail
    if (typeof detail === "string" && detail.trim()) return detail
  }
  return `${fallback} (${response.status})`
}

/** Re-queue a failed, cancelled or paused assignment (POST /api/agent-jobs/{id}/retry). */
export async function retryAssignmentJob(id: string): Promise<AgentJob> {
  const response = await apiFetch(`/api/agent-jobs/${id}/retry`, { method: "POST" })
  if (!response.ok) throw new Error(await jobActionError(response, "Retry failed"))
  return (await response.json()) as AgentJob
}

/** Cancel a queued, running or paused assignment (POST /api/agent-jobs/{id}/cancel). */
export async function cancelAssignmentJob(id: string): Promise<AgentJob> {
  const response = await apiFetch(`/api/agent-jobs/${id}/cancel`, { method: "POST" })
  if (!response.ok) throw new Error(await jobActionError(response, "Cancel failed"))
  return (await response.json()) as AgentJob
}
