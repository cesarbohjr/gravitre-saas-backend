import type { AgentJob } from "@/hooks/use-async-job"
import { apiFetch } from "@/lib/fetcher"
import { actionStats, assignmentFlag, reportedConfidencePercent, reportedIssueText } from "@/lib/assignment-signals"
import {
  type DemoAssignment,
  inferAgentIconForRole,
} from "@/lib/demo-assignments"
const ASSIGNMENTS_REFRESH_KEY = "assignments-list"

export { ASSIGNMENTS_REFRESH_KEY }

const READABLE_KEYS = ["objective", "title", "goal", "task", "description", "prompt", "message", "summary", "query"]

function pickReadableField(node: unknown): string | null {
  if (typeof node === "string") {
    const text = node.trim()
    if (!text) return null
    if (text.startsWith("{") || text.startsWith("[")) return extractReadableFromJson(text) ?? text
    return text
  }
  if (Array.isArray(node)) {
    for (const entry of node) {
      const found = pickReadableField(entry)
      if (found) return found
    }
    return null
  }
  if (node && typeof node === "object") {
    const record = node as Record<string, unknown>
    for (const key of READABLE_KEYS) {
      const found = pickReadableField(record[key])
      if (found) return found
    }
  }
  return null
}

function extractReadableFromJson(text: string): string | null {
  try {
    return pickReadableField(JSON.parse(text))
  } catch {
    return null
  }
}

function handoffLabel(prefix: string): string | null {
  const label = prefix
    .replace(/\bJSON\b/gi, " ")
    .replace(/\bhandoff\b/gi, " ")
    .replace(/[:.\-–—]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
  return label || null
}

/**
 * Job text sometimes arrives as a serialized payload, including department
 * handoff prefixes (`Sales handoff JSON:{...}`). Show the human field inside
 * it rather than raw JSON; fall back to the text with markup stripped.
 */
export function readableAssignmentText(value: string): string {
  const text = value.trim()
  if (!text) return "Agent task"
  const jsonStart = text.search(/[\[{]/)
  if (jsonStart >= 0) {
    const found = extractReadableFromJson(text.slice(jsonStart))
    if (found) {
      const label = handoffLabel(text.slice(0, jsonStart))
      if (label && !found.toLowerCase().startsWith(label.toLowerCase())) {
        return `${label}: ${found}`
      }
      return found
    }
    if (jsonStart > 0) return text
  } else {
    return text
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
    confidence: reportedConfidencePercent(result?.confidence) ?? undefined,
    evidence: {
      toolCalls: countOrNull(result?.tool_call_count ?? result?.toolCallCount ?? result?.tool_calls),
      sources: countOrNull(result?.rag_sources),
      mode: mode ?? null,
      verified: typeof verified === "boolean" ? verified : null,
    },
    blocker: reportedIssueText(job) || undefined,
    approvalPrompt: result?.human_input_prompt?.trim() || undefined,
    resultSummary: resultSummaryFor(status, result?.summary, title, brief),
    agentId: result?.agent_id?.trim() || undefined,
    flag: assignmentFlag(job),
    actions: actionStats(result?.tool_calls),
    jobStatus: job.status,
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
