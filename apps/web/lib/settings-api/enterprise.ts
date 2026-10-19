/**
 * Settings > Enterprise (design p18) data. The redesigned sections read the
 * existing /api/enterprise/* routes (health, suggestions, branding, region,
 * SIEM, workforce signals) plus /api/enterprise/insights/* read models
 * (backend/app/routers/settings_enterprise.py) for knowledge sync, residency,
 * workforce, cost and agent ROI. Pure helpers below are unit tested.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"
import type { IntegrationHealthGrade } from "@/types/api"

export type EnterpriseSectionId =
  | "command-center"
  | "knowledge-sync"
  | "data-residency"
  | "white-label"
  | "workforce"
  | "cost"
  | "agent-roi"
  | "siem"

export const ENTERPRISE_SECTION_IDS: EnterpriseSectionId[] = [
  "command-center",
  "knowledge-sync",
  "data-residency",
  "white-label",
  "workforce",
  "cost",
  "agent-roi",
  "siem",
]

/** Old ?tab= values (CS workspace links, org-context) mapped to the new ?section= ids. */
const LEGACY_TABS: Record<string, EnterpriseSectionId> = {
  cs: "command-center",
  knowledge: "knowledge-sync",
  region: "data-residency",
  branding: "white-label",
  workforce: "workforce",
  cost: "cost",
  roi: "agent-roi",
  siem: "siem",
}

export function resolveEnterpriseSection(section: string | null, legacyTab: string | null): EnterpriseSectionId {
  if (section && (ENTERPRISE_SECTION_IDS as string[]).includes(section)) return section as EnterpriseSectionId
  if (legacyTab && LEGACY_TABS[legacyTab]) return LEGACY_TABS[legacyTab]
  return "command-center"
}

// ---------------------------------------------------------------------------
// Types for /api/enterprise/insights/*
// ---------------------------------------------------------------------------

export type KnowledgeSourceStatus = "healthy" | "syncing" | "failed" | "paused" | "not_configured" | "never_synced"

export interface KnowledgeSource {
  connectorId: string
  name: string
  type: string
  connectorStatus: string | null
  status: KnowledgeSourceStatus
  syncConfigured: boolean
  schedule: string
  docs14d: number
  lastSyncAt: string | null
  lastJobStatus: string | null
  lastError: string | null
  heldReason: string | null
}

export interface KnowledgeSyncOverview {
  ingestionDisabled: boolean
  heldReason: string | null
  sourcesSyncing: number
  sourceCount: number
  documentsIndexed: number | null
  lastSyncAt: string | null
  failedJobs: number
  days: { date: string; documents: number }[]
  totalDocuments: number
  windowDays: number
  sources: KnowledgeSource[]
}

export interface ResidencyRegion {
  id: string
  label: string
  current: boolean
  available: boolean
}

export interface ResidencyOverview {
  region: string
  deploymentRegion: string
  storagePrefix: string
  regions: ResidencyRegion[]
  migrationSupported: boolean
}

export interface WorkforceSummary {
  periodDays: number
  periodStart: string
  periodEnd: string
  tasksCompleted: number
  previousTasksCompleted: number
  changePct: number | null
  activeAgents: number
  newAgents: number
  departmentsTotal: number
  departmentsUsing: number
  departmentsIdle: string[]
  byDepartment: { name: string; tasks: number }[]
  busiestAgents: { agentId: string; name: string; department: string | null; tasks: number }[]
  unattributedTasks: number
  truncated: boolean
}

export interface CostRow {
  id: string
  name: string
  department?: string
  costUsd: number
  calls: number
  runs: number
  agentCount?: number
}

export interface CostAttributionSummary {
  periodStart: string
  periodEnd: string
  source: "model_calls" | "usage_events" | null
  totalCostUsd: number
  agentCount: number
  byAgent: CostRow[]
  byDepartment: CostRow[]
  truncated: boolean
}

export interface AgentRoiRow {
  agentId: string
  name: string
  department: string | null
  tasks: number
  minutesPerTask: number | null
  costUsd: number
  laborValueUsd: number | null
  returnMultiple: number | null
}

export interface AgentRoiSummary {
  periodDays: number
  periodStart: string
  periodEnd: string
  laborUsdPerHour: number | null
  agents: AgentRoiRow[]
  rows: AgentRoiRow[]
  hiddenWithoutEstimate: number
  totals: {
    agentCostUsd: number | null
    laborValueUsd: number | null
    netValueUsd: number | null
    returnMultiple: number | null
  }
  truncated: boolean
}

export interface AgentRoiInputs {
  laborUsdPerHour: number | null
  minutesPerTask: Record<string, number>
}

export const KNOWLEDGE_SYNC_KEY = "/api/enterprise/insights/knowledge-sync"
export const RESIDENCY_KEY = "/api/enterprise/insights/residency"
export const COST_KEY = "/api/enterprise/insights/cost"
export const workforceKey = (days: 7 | 30) => `/api/enterprise/insights/workforce?days=${days}`
export const agentRoiKey = (days: number) => `/api/enterprise/insights/agent-roi?days=${days}`

export const enterpriseInsightsApi = {
  knowledgeSync: () => fetcher<KnowledgeSyncOverview>(KNOWLEDGE_SYNC_KEY),
  residency: () => fetcher<ResidencyOverview>(RESIDENCY_KEY),
  workforce: (days: 7 | 30) => fetcher<WorkforceSummary>(workforceKey(days)),
  cost: () => fetcher<CostAttributionSummary>(COST_KEY),
  agentRoi: (days: number) => fetcher<AgentRoiSummary>(agentRoiKey(days)),
  updateAgentRoiInputs: async (body: {
    laborUsdPerHour?: number
    clearRate?: boolean
    minutesPerTask?: Record<string, number | null>
  }): Promise<AgentRoiInputs> => {
    const response = await apiFetch("/api/enterprise/insights/agent-roi", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(extractApiErrorMessage(payload) || `Request failed: ${response.status}`)
    return payload as AgentRoiInputs
  },
}

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

export function formatUsd(value: number | null | undefined): string {
  const n = Number(value ?? 0)
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: n >= 100 ? 0 : 2,
    maximumFractionDigits: n >= 100 ? 0 : 2,
  }).format(n)
}

export function formatMultiple(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null
  return `${value >= 10 ? Math.round(value) : Math.round(value * 10) / 10}×`
}

/** Design's band label for the backend grade (at_risk is shown as Watch). */
export function healthBand(grade: IntegrationHealthGrade): { label: string; tone: "green" | "amber" | "red" } {
  if (grade === "healthy") return { label: "Healthy", tone: "green" }
  if (grade === "at_risk") return { label: "Watch", tone: "amber" }
  return { label: "Critical", tone: "red" }
}

/** Bar tone for a 0 to 100 dimension score, on the same thresholds as the grade. */
export function scoreTone(score: number): "green" | "amber" | "red" {
  if (score >= 85) return "green"
  if (score >= 65) return "amber"
  return "red"
}

export const DIMENSION_LABELS: Record<string, string> = {
  connectorsLive: "Connector health",
  workflowSuccessRate: "Workflow success",
  agentUtilization: "Agent use",
  approvalLatency: "Approval speed",
}

/** Recommendation level from the backend's suggestion priority (90 / 80 / 65). */
export function recommendationLevel(priority: number): { label: "HIGH" | "MEDIUM" | "LOW"; tone: "red" | "amber" | "mute" } {
  if (priority >= 85) return { label: "HIGH", tone: "red" }
  if (priority >= 70) return { label: "MEDIUM", tone: "amber" }
  return { label: "LOW", tone: "mute" }
}

export function sourceStatusMeta(status: KnowledgeSourceStatus): {
  label: string
  tone: "green" | "blue" | "red" | "neutral" | "amber"
  cta: "Sync now" | "Retry" | "Resume" | null
} {
  switch (status) {
    case "healthy":
      return { label: "Healthy", tone: "green", cta: "Sync now" }
    case "syncing":
      return { label: "Syncing", tone: "blue", cta: null }
    case "failed":
      return { label: "Failed", tone: "red", cta: "Retry" }
    case "paused":
      return { label: "Paused", tone: "neutral", cta: "Resume" }
    case "not_configured":
      return { label: "Not set up", tone: "amber", cta: null }
    default:
      return { label: "Not synced yet", tone: "neutral", cta: "Sync now" }
  }
}

/** Bar heights for the 14 day chart: zero days get a short red stub, like the design. */
export function ingestBars(days: { date: string; documents: number }[]): { date: string; documents: number; heightPct: number; zero: boolean }[] {
  const max = Math.max(0, ...days.map((d) => d.documents))
  return days.map((d) => ({
    ...d,
    zero: d.documents === 0,
    heightPct: d.documents === 0 || max === 0 ? 3 : Math.max(4, Math.round((d.documents / max) * 100)),
  }))
}

export function changeCopy(changePct: number | null, periodDays: 7 | 30): { text: string; tone: "green" | "red" | "mute" } | null {
  if (changePct == null) return null
  const span = periodDays === 7 ? "last week" : "the 30 days before"
  if (changePct === 0) return { text: `Same as ${span}`, tone: "mute" }
  return changePct > 0
    ? { text: `${changePct}% more than ${span}`, tone: "green" }
    : { text: `${Math.abs(changePct)}% fewer than ${span}`, tone: "red" }
}

/** Shares of a total as percentages for the stacked bar (rows with no cost get 0). */
export function costShares<T extends { costUsd: number }>(rows: T[], total: number): (T & { sharePct: number })[] {
  return rows.map((row) => ({ ...row, sharePct: total > 0 ? (row.costUsd / total) * 100 : 0 }))
}

export function parsePositiveNumber(raw: string, max: number): number | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const n = Number(trimmed)
  if (!Number.isFinite(n) || n <= 0 || n > max) return null
  return Math.round(n * 100) / 100
}

export const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

/** Custom domain check before saving: a plain host name like ai.yourcompany.com. */
export function isValidDomain(value: string): boolean {
  const v = value.trim().toLowerCase()
  if (!v) return true
  return /^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(v)
}
