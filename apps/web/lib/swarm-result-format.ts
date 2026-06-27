import type { AgentSwarmRun, AgentSwarmSubtask } from "@/types/api"

/** Strip code fences and noisy JSON blobs for user-facing swarm summaries. */
export function formatSwarmReadableText(raw: string | null | undefined, maxLen = 600): string {
  if (!raw?.trim()) return ""
  let text = raw.trim()
  text = text.replace(/```[\s\S]*?```/g, " ")
  text = text.replace(/`([^`]+)`/g, "$1")
  if (/^\s*[\[{]/.test(text) && text.length > 120) {
    try {
      const parsed = JSON.parse(text) as Record<string, unknown>
      const parts = ["summary", "finding", "answer", "recommendedAction", "recommended_action", "message"]
        .map((key) => parsed[key])
        .filter((v): v is string => typeof v === "string" && v.trim().length > 0)
      if (parts.length > 0) text = parts.join(" — ")
    } catch {
      /* keep prose */
    }
  }
  text = text.replace(/\s+/g, " ").trim()
  if (text.length > maxLen) return `${text.slice(0, maxLen - 1)}…`
  return text
}

export function subtaskReadableSummary(subtask: AgentSwarmSubtask): string | null {
  const result = subtask.result
  if (!result || typeof result !== "object") return null
  const record = result as Record<string, unknown>
  const candidates = [
    record.summary,
    record.finding,
    record.answer,
    record.recommendedAction,
    record.recommended_action,
    record.action_description,
  ]
  for (const value of candidates) {
    if (typeof value === "string" && value.trim()) {
      return formatSwarmReadableText(value)
    }
  }
  return null
}

export function extractSwarmNextSteps(run: AgentSwarmRun): string[] {
  const steps = new Set<string>()
  for (const subtask of run.subtasks ?? []) {
    const result = subtask.result
    if (!result || typeof result !== "object") continue
    const record = result as Record<string, unknown>
    const actions = record.recommended_actions ?? record.recommendedActions
    if (Array.isArray(actions)) {
      for (const action of actions) {
        if (typeof action === "string" && action.trim()) steps.add(formatSwarmReadableText(action, 200))
      }
    }
    const single = record.recommendedAction ?? record.recommended_action
    if (typeof single === "string" && single.trim()) steps.add(formatSwarmReadableText(single, 200))
  }
  const aggregate = run.aggregateResult
  if (aggregate && typeof aggregate === "object") {
    const finalRec = (aggregate as Record<string, unknown>).finalRecommendation
    if (typeof finalRec === "string" && finalRec.trim()) {
      steps.add(formatSwarmReadableText(finalRec, 200))
    }
  }
  if (run.finalRecommendation?.trim()) {
    steps.add(formatSwarmReadableText(run.finalRecommendation, 200))
  }
  return Array.from(steps).slice(0, 5)
}

export interface CouncilRoundView {
  round: number
  reasoning?: string
  keyPoints: string[]
  concerns: string[]
}

export function extractCouncilRounds(run: AgentSwarmRun): CouncilRoundView[] {
  const aggregate = run.aggregateResult
  if (!aggregate || typeof aggregate !== "object") return []
  const rounds = (aggregate as Record<string, unknown>).debateRounds
  if (!Array.isArray(rounds)) return []
  return rounds
    .map((entry, index): CouncilRoundView | null => {
      if (!entry || typeof entry !== "object") return null
      const row = entry as Record<string, unknown>
      const keyPoints = Array.isArray(row.keyPoints)
        ? row.keyPoints.filter((p): p is string => typeof p === "string")
        : []
      const concerns = Array.isArray(row.concerns)
        ? row.concerns.filter((p): p is string => typeof p === "string")
        : []
      const reasoning =
        typeof row.reasoning === "string" ? formatSwarmReadableText(row.reasoning, 400) : undefined
      return {
        round: typeof row.round === "number" ? row.round : index + 1,
        ...(reasoning ? { reasoning } : {}),
        keyPoints: keyPoints.map((p) => formatSwarmReadableText(p, 160)),
        concerns: concerns.map((p) => formatSwarmReadableText(p, 160)),
      }
    })
    .filter((row): row is CouncilRoundView => row !== null)
}

export function extractDissentingOpinions(run: AgentSwarmRun): string[] {
  const aggregate = run.aggregateResult
  if (!aggregate || typeof aggregate !== "object") return []
  const dissent = (aggregate as Record<string, unknown>).dissentingOpinions
  if (!Array.isArray(dissent)) return []
  return dissent
    .filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    .map((item) => formatSwarmReadableText(item, 200))
}
