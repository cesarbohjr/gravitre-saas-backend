import type { AgentJob } from "@/hooks/use-async-job"
import { apiFetch } from "@/lib/fetcher"
import {
  type DemoAssignment,
  inferAgentIconForRole,
} from "@/lib/demo-assignments"
const ASSIGNMENTS_REFRESH_KEY = "assignments-list"

export { ASSIGNMENTS_REFRESH_KEY }

const READABLE_KEYS = ["objective", "title", "goal", "task", "description", "prompt", "message", "summary", "query"]

/**
 * Job text sometimes arrives as a serialized payload. Show the human field
 * inside it rather than raw JSON; fall back to the text with markup stripped.
 */
export function readableAssignmentText(value: string): string {
  const text = value.trim()
  if (!text.startsWith("{") && !text.startsWith("[")) return text
  try {
    const parsed: unknown = JSON.parse(text)
    const pick = (node: unknown): string | null => {
      if (typeof node === "string") return node.trim() || null
      if (Array.isArray(node)) {
        for (const entry of node) {
          const found = pick(entry)
          if (found) return found
        }
        return null
      }
      if (node && typeof node === "object") {
        const record = node as Record<string, unknown>
        for (const key of READABLE_KEYS) {
          const found = pick(record[key])
          if (found) return found
        }
      }
      return null
    }
    const found = pick(parsed)
    if (found) return found
  } catch {
    /* not JSON — strip below */
  }
  const stripped = text.replace(/[{}\[\]"]/g, " ").replace(/\s+/g, " ").trim()
  return stripped || "Agent task"
}

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

function countOrNull(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (Array.isArray(value)) return value.length
  return null
}

export function resultSummaryFor(
  status: DemoAssignment["status"],
  summary: string | undefined,
  title: string,
  brief?: string,
): string | undefined {
  if (status !== "completed" && status !== "needs_approval") return undefined
  const text = summary ? readableAssignmentText(summary).trim() : ""
  if (!text || text === title || text === brief || text === "Agent task") return undefined
  return text
}

function mapJobToAssignment(job: AgentJob): DemoAssignment {
  const result = job.result
  const brief = readableAssignmentText(
    result?.task?.description?.trim() ||
      result?.finding_description?.trim() ||
      result?.summary?.trim() ||
      "Agent task",
  )
  const title = readableAssignmentText(result?.action_title?.trim() || brief).slice(0, 96)
  const agentName = result?.agent_name?.trim() || "Agent"
  const progressPercent = result?.progress_percent
  const status = mapJobStatus(job)
  const mode = result?.execution_mode ?? result?.executionMode ?? null
  const verified = result?.execution_verified ?? result?.executionVerified

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
    status,
    // Only a reported percentage is shown; unknown progress stays unknown.
    progress:
      status === "completed" || status === "needs_approval"
        ? 100
        : typeof progressPercent === "number"
          ? Math.round(progressPercent * 100)
          : Number.NaN,
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
    createdAt: job.createdAt || "",
    createdAtIso: job.createdAt || undefined,
    completedAt: job.finishedAt ?? undefined,
    outputTypes: ["Task"],
    destination: "Review",
    confidence: result?.confidence ? Math.round(result.confidence * 100) : undefined,
    evidence: {
      toolCalls: countOrNull(result?.tool_call_count ?? result?.toolCallCount ?? result?.tool_calls),
      sources: countOrNull(result?.rag_sources),
      mode: mode ?? null,
      verified: typeof verified === "boolean" ? verified : null,
    },
    blocker: job.error?.trim() || result?.error?.trim() || undefined,
    approvalPrompt: result?.human_input_prompt?.trim() || undefined,
    resultSummary: resultSummaryFor(status, result?.summary, title, brief),
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
