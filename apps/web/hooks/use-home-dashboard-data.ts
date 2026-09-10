"use client"

import useSWR from "swr"
import {
  architectureAdminApi,
  intelligenceApi,
  approvalsApi,
  metricsApi,
  agentsApi,
} from "@/lib/api"
import {
  normalizeAiOsStatus,
  normalizeMetricsOverview,
} from "@/lib/dashboard/normalize-metrics"
import type { DashboardRange } from "@/lib/dashboard/types"
import type { Agent } from "@/types/api"

export type HomeDashboardData = {
  agents: Agent[]
  activeAgents: number | null
  agentTotal: number | null
  agentStatusCounts: {
    active: number
    idle: number
    processing: number
    error: number
  } | null
  metrics: ReturnType<typeof normalizeMetricsOverview>
  aiOs: ReturnType<typeof normalizeAiOsStatus>
  pendingApprovals: number
  pendingApprovalItems: Array<{ id: string; title?: string }>
  avgConfidence: number | null
  queryRows: number
  queryRowsNeeded: number
  workflowRows: number
  workflowRowsNeeded: number
  hasLearningSnapshot: boolean
  revenueRisks: Array<{ id: string; title: string; summary: string }>
  predictiveSummary: string | null
  readyModelCount: number | null
  learningVelocity: string | null
  mostUsedModel: string | null
}

function computeMostUsedModel(agents: Agent[]): string | null {
  const counts = new Map<string, number>()
  for (const agent of agents) {
    const model = agent.model?.trim()
    if (!model) continue
    counts.set(model, (counts.get(model) ?? 0) + 1)
  }
  if (counts.size === 0) return null
  let best = ""
  let bestCount = 0
  for (const [model, count] of counts) {
    if (count > bestCount) {
      best = model
      bestCount = count
    }
  }
  return best || null
}

function formatModelLabel(model: string): string {
  const normalized = model.trim()
  if (!normalized) return "—"
  if (/^gpt-4o$/i.test(normalized)) return "GPT-4o"
  if (/^gpt-4o-mini$/i.test(normalized)) return "GPT-4o mini"
  if (/^gpt-4/i.test(normalized)) return normalized.replace(/^gpt-/i, "GPT-")
  return normalized
}

export { formatModelLabel }

function rangeToApi(range: DashboardRange): string {
  // Overview endpoint accepts 7d | 30d | 90d only.
  if (range === "30d") return "30d"
  if (range === "90d") return "90d"
  return "7d"
}

export function useHomeDashboardData(enabled: boolean, range: DashboardRange = "7d") {
  const { data: learning } = useSWR(
    enabled ? "home/learning-progress" : null,
    () => intelligenceApi.learningProgress(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: trust } = useSWR(
    enabled ? "home/trust" : null,
    () => intelligenceApi.trustSummary({ periodDays: 7 }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: businessImpact } = useSWR(
    enabled ? "home/business-impact" : null,
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: aiOsRaw } = useSWR(
    enabled ? "home/ai-os" : null,
    () => architectureAdminApi.aiOsStatus(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: predictive } = useSWR(
    enabled ? "home/predictive" : null,
    () => architectureAdminApi.predictiveOps(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: learningLive } = useSWR(
    enabled ? "home/learning-live" : null,
    () => intelligenceApi.learningLiveDashboard(),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: 30_000 },
  )
  const { data: learningStatus } = useSWR(
    enabled ? "home/learning-status" : null,
    () => architectureAdminApi.learningStatus(),
    { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: 30_000 },
  )
  const { data: approvalsData } = useSWR(
    enabled ? "home/approvals" : null,
    () => approvalsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: metricsRaw } = useSWR(
    enabled ? `home/metrics-overview:${rangeToApi(range)}` : null,
    () => metricsApi.overview(rangeToApi(range)),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: agentsList } = useSWR(
    enabled ? "home/agents-list" : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  const agents = agentsList?.agents ?? []
  const activeAgents = agents.filter((agent) => {
    const status = String(agent.status ?? "").toLowerCase()
    return status === "active" || status === "processing" || status === "running"
  }).length
  const agentStatusCounts =
    agents.length > 0
      ? {
          active: agents.filter((a) => String(a.status ?? "").toLowerCase() === "active").length,
          idle: agents.filter((a) => String(a.status ?? "").toLowerCase() === "idle").length,
          processing: agents.filter((a) => {
            const s = String(a.status ?? "").toLowerCase()
            return s === "processing" || s === "running"
          }).length,
          error: agents.filter((a) => String(a.status ?? "").toLowerCase() === "error").length,
        }
      : null

  const pendingApprovalItems =
    approvalsData?.approvals?.filter((item) => item.status === "pending") ?? []
  const avgConfidence =
    typeof trust?.avg_confidence === "number"
      ? Math.round(trust.avg_confidence * 100)
      : typeof trust?.avgConfidence === "number"
        ? Math.round(trust.avgConfidence * 100)
        : null

  const data: HomeDashboardData = {
    agents,
    activeAgents: agents.length > 0 ? activeAgents : null,
    agentTotal: agents.length > 0 ? agents.length : null,
    agentStatusCounts,
    metrics: normalizeMetricsOverview(metricsRaw),
    aiOs: normalizeAiOsStatus(aiOsRaw),
    pendingApprovals: pendingApprovalItems.length,
    pendingApprovalItems: pendingApprovalItems.map((item) => ({
      id: item.id,
      title: item.workflow_name ?? item.workflowName ?? `Run ${item.id.slice(0, 8)}`,
    })),
    avgConfidence,
    queryRows: learning?.queryRows ?? 0,
    queryRowsNeeded: learning?.queryRowsNeeded ?? 50,
    workflowRows: learning?.workflowRows ?? 0,
    workflowRowsNeeded: learning?.workflowRowsNeeded ?? 30,
    hasLearningSnapshot: Boolean(learning?.hasAnySnapshot),
    revenueRisks: businessImpact?.revenueRiskItems ?? [],
    predictiveSummary: typeof predictive?.summary === "string" ? predictive.summary : null,
    readyModelCount:
      typeof learningLive?.ready_model_count === "number" ? learningLive.ready_model_count : null,
    learningVelocity:
      typeof learningStatus?.learning_velocity === "string"
        ? learningStatus.learning_velocity
        : null,
    mostUsedModel: agents.length > 0 ? computeMostUsedModel(agents) : null,
  }

  return data
}
