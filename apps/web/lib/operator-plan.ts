import type { AgentJobResult } from "@/hooks/use-async-job"

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export type OperatorInsightSection = {
  id: string
  type: "summary" | "root-cause" | "analysis" | "discovery"
  title: string
  content: string
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
      title: "Analysis Summary",
      content:
        result.analysis_summary ||
        result.summary ||
        result.answer ||
        "Analysis complete.",
    },
    {
      id: "finding",
      type: "root-cause",
      title: "Finding",
      content: result.finding_description || "No specific findings.",
    },
    ...traceSections,
  ]

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
