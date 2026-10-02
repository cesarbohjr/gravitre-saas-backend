import { apiFetch, fetcher } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"

export type DepartmentContract = {
  outcome: { problem: string; target_outcome: string; success_criteria: string[]; kpis: Array<{ key: string; label: string; unit: string; direction: string; target?: number | string | null }> }
  providers: string[]
  dashboard: { title: string; metrics: Array<{ kpi_key: string; label: string; visualization: string; description: string }> }
  dataset: { entities: Array<{ name: string; source: string; primary_key: string; fields: string[] }>; metrics: Array<{ key: string; label: string; formula: string; unit: string }> }
  plays: Array<{ key: string; name: string; description: string; kpiKeys: string[]; runtimeInputs: string[]; trigger: { type?: string; cadence?: string; event?: string } }>
  agents: Array<{ name: string; purpose: string; capabilities: string[] }>
  knowledge: Array<{ title: string; purpose: string }>
}
export type DepartmentMeasurement = { evidenceId: string; metricKey: string; playKey: string; baselineValue: number; resultValue: number; measuredAt: string; verificationMethod: string; sourceRecords: Array<{ system: string; record_type: string; record_id: string }> }
export type DepartmentWorkspace = {
  asset: { id: string; slug: string; title: string; department?: string; certificationLevel?: string }
  install?: { id: string; version: number; pilot: boolean; installedAt?: string; agentIds: string[]; workflowIds: string[]; plays: Array<{ playKey?: string; workflowId?: string }>; capabilityPackageIds: string[] }
  contract: DepartmentContract
  measurements: DepartmentMeasurement[]
  sources: Array<{ id: string; title: string; status: string }>
  recentRuns: Array<{ id: string; status: string; run_type: string; environment: string; created_at: string; workflow_id: string }>
  activityLimit: number
}
export type DepartmentReadiness = {
  slug: string; title: string; department: string; assetId?: string; deployed: boolean
  status: string; certificationLevel?: string; storedCertificationLevel?: string; fixturePassed: boolean
  playCount?: number; agentCount?: number; kpiCount?: number; requiredSystems?: string[]
  runtimeEvidenceProviders?: string[]; measuredOutcomeCount?: number; publishReady: boolean; nextGate: string
  blockingFindingCodes: string[]
}
export type PortfolioReadiness = { source: string; packCount: number; deployedPackCount: number; governedCount: number; productionVerifiedCount: number; outcomeVerifiedCount: number; packs: DepartmentReadiness[] }
export const marketplace3Api = {
  readiness: () => fetcher<PortfolioReadiness>("/api/marketplace/platform/marketplace3/portfolio-readiness"),
  workspace: (slug: string) => fetcher<DepartmentWorkspace>(`/api/marketplace/assets/${encodeURIComponent(slug)}/workspace`),
  blueprint: (slug: string) => fetcher<DepartmentWorkspace>(`/api/marketplace/platform/assets/${encodeURIComponent(slug)}/marketplace3/blueprint`),
  action: async (slug: string, action: "install-pilot" | "certify" | "certify-run" | "promote", body: unknown) => {
    const response = await apiFetch(`/api/marketplace/platform/assets/${encodeURIComponent(slug)}/marketplace3/${action}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) })
    const data = await response.json()
    if (!response.ok) throw new Error(extractApiErrorMessage(data) ?? "Department action failed")
    return data
  },
}
export const DEPARTMENT_DESIGNS: Record<string, { focus: string; accent: string; icon: "service" | "security" | "revenue" | "success" | "finance" | "marketing" | "people" | "executive" }> = {
  "msp-service-desk-3": { focus: "Service reliability", accent: "#38bdf8", icon: "service" },
  "security-operations-3": { focus: "Exposure & response", accent: "#a78bfa", icon: "security" },
  "revenue-operations-3": { focus: "Pipeline & forecast", accent: "#34d399", icon: "revenue" },
  "customer-success-support-3": { focus: "Customer health & retention", accent: "#22d3ee", icon: "success" },
  "finance-operations-3": { focus: "Cash & reconciliation", accent: "#fbbf24", icon: "finance" },
  "marketing-operations-3": { focus: "Demand & attribution", accent: "#fb7185", icon: "marketing" },
  "people-it-operations-3": { focus: "People & access", accent: "#818cf8", icon: "people" },
  "executive-command-center-3": { focus: "Portfolio decisions", accent: "#f97316", icon: "executive" },
}
const certificateLabels: Record<string, string> = { governed: "Governed", tested: "Tested", production_verified: "Production verified", outcome_verified: "Outcome verified" }
export const certificateLabel = (level?: string) => certificateLabels[level ?? ""] ?? "Uncertified"
export const parseEvidenceIds = (value: string): string[] => {
  const ids = [...new Set(value.split(/[\s,]+/).filter(Boolean))]
  if (ids.length > 100 || ids.some(id => !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id))) throw new Error("Use up to 100 valid record UUIDs, separated by commas or new lines.")
  return ids
}
