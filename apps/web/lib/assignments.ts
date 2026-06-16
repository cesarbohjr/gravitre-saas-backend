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
  let assignment = buildQueuedAssignment(input)

  try {
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

    if (response.ok) {
      const job = (await response.json()) as AgentJob
      if (job?.jobId) {
        assignment = buildQueuedAssignment(input, job.jobId)
      }
    }
  } catch {
    // Demo/offline fallback keeps the optimistic queued row.
  }

  registerDemoAssignment(assignment)
  return { id: assignment.id, assignment }
}

export { avatarGradient }
