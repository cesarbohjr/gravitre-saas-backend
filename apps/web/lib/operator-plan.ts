import type { AgentJobResult } from "@/hooks/use-async-job"

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export type OperatorInsightSection = {
  id: string
  type:
    | "summary"
    | "root-cause"
    | "analysis"
    | "discovery"
    | "reasoning"
    | "actions"
    | "prevention"
    | "evidence"
  title: string
  content: string
  actions?: { id: string; label: string; priority: "high" | "medium" | "low" }[]
}

export function resolveSessionIdForJob(taskId: string): string | undefined {
  return UUID_RE.test(taskId) ? taskId : undefined
}

export function buildOperatorJobContext(
  activeContext: string,
  extra?: Record<string, unknown>,
): Record<string, unknown> {
  return {
    entityType: activeContext.split("-")[0],
    entityId: activeContext,
    ...extra,
  }
}

export function isBackendUnavailableError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err)
  return /FASTAPI|configuration|502|503|Backend request failed|fetch failed|Failed to fetch|ECONNREFUSED/i.test(
    msg,
  )
}

export function describeOperatorJobError(err: unknown): string {
  if (err instanceof Error && err.message.trim()) return err.message.trim()
  return "Unknown error"
}

export function buildFindingsFromJobResult(result: AgentJobResult): OperatorInsightSection[] {
  const trace = Array.isArray(result.react_trace) ? result.react_trace : []
  const traceSections: OperatorInsightSection[] = []

  for (let index = 0; index < trace.length; index += 1) {
    const step = trace[index]
    if (!step || typeof step !== "object") continue
    const record = step as Record<string, unknown>
    const tool = String(record.toolName || record.action || "").trim()
    const content = String(record.observation || record.thought || "").trim()
    if (!content) continue
    traceSections.push({
      id: `trace-${index}`,
      type: tool ? "discovery" : "analysis",
      title: tool ? `Tool: ${tool}` : `Reasoning step ${record.iteration ?? index + 1}`,
      content,
    })
  }

  const sections: OperatorInsightSection[] = [
    {
      id: "summary",
      type: "summary",
      title: "What Happened",
      content:
        result.analysis_summary ||
        result.summary ||
        result.answer ||
        "Analysis complete.",
    },
    {
      id: "finding",
      type: "root-cause",
      title: "Why It Happened",
      content: result.finding_description || "No specific findings.",
    },
    ...traceSections,
  ]

  const recommended = Array.isArray(result.recommended_actions)
    ? result.recommended_actions.filter((item) => typeof item === "string" && item.trim())
    : []

  if (recommended.length > 0) {
    sections.push({
      id: "actions",
      type: "actions",
      title: "How to Fix It",
      content: result.action_description || "Recommended remediation steps from the analysis:",
      actions: recommended.map((label, index) => ({
        id: `action-${index + 1}`,
        label: String(label),
        priority: index === 0 ? "high" : index === 1 ? "medium" : "low",
      })),
    })
    sections.push({
      id: "prevention",
      type: "prevention",
      title: "Prevention",
      content:
        result.action_title
          ? `Ongoing mitigation: ${result.action_title}. Monitor similar failures and adjust thresholds before peak load.`
          : "Monitor for repeat failures, tune timeouts ahead of peak hours, and enable alerts on connector latency.",
    })
  }

  if (result.persona) {
    sections.push({
      id: "persona",
      type: "analysis",
      title: "Agent persona",
      content: String(result.persona),
    })
  }

  return sections
}
