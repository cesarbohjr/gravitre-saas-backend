import type { Agent } from "@/types/api"
import type { IntelligenceCoreDepartment } from "@/lib/api"
import type { IntelligenceMapLens } from "./intelligence-map-lens"
import type { IntelligenceMapSelection } from "./intelligence-map"
import { readString } from "@/lib/intelligence/helpers"
import { normalizeDeptKey, signalDepartmentKey } from "./map-topology"

export type AskMapFocus = {
  lens: IntelligenceMapLens
  highlightNodeIds: string[]
  selection: IntelligenceMapSelection
}

const LENS_KEYWORDS: Record<IntelligenceMapLens, string[]> = {
  knows: ["know", "knowledge", "memory", "entity", "relationship", "learned what"],
  learns: ["learn", "learning", "training", "train", "model", "readiness"],
  predicts: [
    "predict",
    "risk",
    "warning",
    "attention",
    "slow",
    "fail",
    "failure",
    "oauth",
    "expir",
    "error",
    "why",
  ],
  acts: ["agent", "workflow", "active", "running", "execut", "doing", "hubspot create"],
  improves: ["improve", "outcome", "roi", "resolved", "win", "impact", "result"],
}

const DEPT_KEYWORDS: Record<string, string[]> = {
  sales: ["sales", "hubspot", "pipeline", "deal", "sdr", "crm"],
  support: ["support", "ticket", "zendesk", "customer success"],
  finance: ["finance", "billing", "stripe", "invoice", "payment"],
  marketing: ["marketing", "campaign", "ads", "google ads"],
  operations: ["operations", "workflow", "capacity", "ops"],
  hr: ["hr", "hiring", "recruit"],
}

function countKeywordHits(text: string, keywords: string[]): number {
  return keywords.reduce((sum, word) => (text.includes(word) ? sum + 1 : sum), 0)
}

function pickLens(question: string): IntelligenceMapLens {
  const q = question.toLowerCase()
  let best: IntelligenceMapLens = "predicts"
  let bestScore = 0
  for (const [lens, keywords] of Object.entries(LENS_KEYWORDS) as [IntelligenceMapLens, string[]][]) {
    const score = countKeywordHits(q, keywords)
    if (score > bestScore) {
      bestScore = score
      best = lens
    }
  }
  return best
}

function matchDepartments(question: string, departments: IntelligenceCoreDepartment[]): string[] {
  const q = question.toLowerCase()
  const ids: string[] = []
  for (const dept of departments) {
    const key = normalizeDeptKey(dept.id)
    const keywords = DEPT_KEYWORDS[key] ?? [key.replace(/_/g, " ")]
    if (countKeywordHits(q, keywords) > 0 || q.includes(key.replace(/_/g, " "))) {
      ids.push(`dept:${dept.id}`)
    }
  }
  return ids
}

function matchAgents(question: string, agents: Agent[]): string[] {
  const q = question.toLowerCase()
  return agents
    .filter(
      (agent) =>
        q.includes(agent.name.toLowerCase()) ||
        q.includes(agent.department.toLowerCase()) ||
        q.includes((agent.role ?? "").toLowerCase()),
    )
    .slice(0, 4)
    .map((agent) => `agent:${agent.id}`)
}

function matchSignals(
  question: string,
  signals: Record<string, unknown>[],
): { nodeIds: string[]; signal: Record<string, unknown> | null } {
  const q = question.toLowerCase()
  for (const signal of signals) {
    const title = readString(signal.title, "").toLowerCase()
    const summary = readString(signal.summary, "").toLowerCase()
    if (
      (title && q.includes(title.slice(0, Math.min(title.length, 12)))) ||
      title.split(/\s+/).some((word) => word.length > 4 && q.includes(word)) ||
      summary.split(/\s+/).some((word) => word.length > 5 && q.includes(word))
    ) {
      const id = readString(signal.id, readString(signal.title, "signal"))
      return { nodeIds: [`signal:${id}`], signal }
    }
  }
  for (const signal of signals) {
    const deptKey = signalDepartmentKey(signal)
    if (deptKey && q.includes(deptKey.replace(/_/g, " "))) {
      const id = readString(signal.id, readString(signal.title, "signal"))
      return { nodeIds: [`signal:${id}`, `dept:${deptKey}`], signal }
    }
  }
  return { nodeIds: [], signal: null }
}

/**
 * Heuristic focus resolver for Phase E — maps a natural-language hub question
 * to a lens, highlighted node ids, and optional context-panel selection.
 * Uses keyword matching only; does not invent nodes not present in inputs.
 */
export function resolveAskMapFocus(
  question: string,
  context: {
    departments: IntelligenceCoreDepartment[]
    agents: Agent[]
    signals: Record<string, unknown>[]
  },
): AskMapFocus {
  const lens = pickLens(question)
  const q = question.toLowerCase()
  const deptIds = matchDepartments(question, context.departments)
  let agentIds =
    lens === "acts" || q.includes("agent") ? matchAgents(question, context.agents) : []
  if (agentIds.length === 0 && (lens === "acts" || q.includes("agent"))) {
    agentIds = context.agents
      .filter((agent) => agent.status === "active" || q.includes("agent"))
      .slice(0, 4)
      .map((agent) => `agent:${agent.id}`)
  }
  const { nodeIds: signalIds, signal } = matchSignals(question, context.signals)

  const highlightNodeIds = [...new Set([...deptIds, ...agentIds, ...signalIds])]

  let selection: IntelligenceMapSelection = null
  if (signal) {
    selection = { kind: "signal", signal }
  } else if (agentIds.length > 0) {
    const agent = context.agents.find((a) => `agent:${a.id}` === agentIds[0])
    if (agent) selection = { kind: "agent", agent }
  } else if (deptIds.length > 0) {
    const dept = context.departments.find((d) => `dept:${d.id}` === deptIds[0])
    if (dept) selection = { kind: "department", department: dept }
  }

  return { lens, highlightNodeIds, selection }
}
