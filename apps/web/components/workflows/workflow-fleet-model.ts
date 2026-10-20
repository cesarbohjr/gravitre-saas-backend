/**
 * Workflows page model: normalizes GET /api/workflows rows (run summary,
 * departments and canvas nodes included) and derives the counts, filters and
 * sort orders the page shows. Pure functions so the rules stay testable.
 */
export type WorkflowState = "active" | "paused" | "draft" | "error"
export type WorkflowSegment = "all" | "active" | "paused" | "failing" | "draft"
export type WorkflowSort = "recent" | "name" | "success" | "runs"

export type RecentRun = { status: string; createdAt?: string | null }

export type FleetWorkflow = {
  id: string
  name: string
  description: string
  status: WorkflowState
  environment: string
  departments: string[]
  lastRun: string | null
  lastRunStatus: string | null
  isRunning: boolean
  successRate: number | null
  runCount: number
  recentRuns: RecentRun[]
  steps: string[]
  /** False when the run history read was cut short and no stored totals exist: runCount is a lower bound. */
  runStatsComplete: boolean
}

function normalizeStatus(raw: unknown): WorkflowState {
  const value = String(raw ?? "draft").toLowerCase()
  if (value === "active" || value === "paused" || value === "draft" || value === "error") return value
  if (value === "inactive" || value === "archived") return "paused"
  return "draft"
}

function stepNames(nodes: unknown): string[] {
  if (!Array.isArray(nodes)) return []
  return nodes
    .filter((node): node is Record<string, unknown> => Boolean(node) && typeof node === "object")
    .map((node) => {
      const data = (node.data ?? {}) as Record<string, unknown>
      return String(node.name ?? node.title ?? data.label ?? data.title ?? node.label ?? "").trim()
    })
    .filter(Boolean)
}

export function normalizeWorkflow(input: Record<string, unknown>): FleetWorkflow {
  const runCount = Number(input.runCount ?? input.run_count ?? 0) || 0
  const rate = typeof input.successRate === "number" ? input.successRate : Number.parseFloat(String(input.successRate ?? ""))
  const recent = Array.isArray(input.recentRuns) ? (input.recentRuns as unknown[]) : []
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "Workflow"),
    description: String(input.description ?? input.goal ?? ""),
    status: normalizeStatus(input.status),
    environment: String(input.environment ?? "production"),
    departments: Array.isArray(input.departments) ? (input.departments as unknown[]).map(String).filter(Boolean) : [],
    lastRun: typeof input.lastRun === "string" && input.lastRun && input.lastRun !== "Never" ? input.lastRun : null,
    lastRunStatus: typeof input.lastRunStatus === "string" ? input.lastRunStatus : null,
    isRunning: Boolean(input.isRunning ?? input.is_running ?? false),
    // A success rate only means something once the workflow has run, and only
    // when the backend computed it from the whole history (null otherwise).
    successRate: runCount > 0 && input.successRate !== null && Number.isFinite(rate) ? Math.round(rate) : null,
    runCount,
    recentRuns: recent
      .filter((run): run is Record<string, unknown> => Boolean(run) && typeof run === "object")
      .map((run) => ({ status: String(run.status ?? "unknown"), createdAt: (run.createdAt as string | undefined) ?? null })),
    steps: stepNames(input.nodes),
    runStatsComplete: input.runStatsComplete !== false,
  }
}

export function normalizeWorkflows(payload: unknown): FleetWorkflow[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.workflows) ? model.workflows : Array.isArray(model.data) ? model.data : []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map(normalizeWorkflow)
    .filter((item) => item.id.length > 0)
}

/** Failing: the workflow is in an error state, or its latest run failed. */
export function isFailing(workflow: FleetWorkflow): boolean {
  return workflow.status === "error" || workflow.lastRunStatus === "failed"
}

export function segmentOf(workflow: FleetWorkflow): Exclude<WorkflowSegment, "all"> {
  if (isFailing(workflow)) return "failing"
  if (workflow.status === "error") return "failing"
  return workflow.status
}

export type FleetSummary = Record<Exclude<WorkflowSegment, "all">, number> & { all: number; running: number }

export function summarizeFleet(workflows: FleetWorkflow[]): FleetSummary {
  const out: FleetSummary = { all: workflows.length, active: 0, paused: 0, failing: 0, draft: 0, running: 0 }
  for (const workflow of workflows) {
    if (workflow.isRunning) out.running += 1
    if (workflow.status === "active") out.active += 1
    if (workflow.status === "paused") out.paused += 1
    if (workflow.status === "draft") out.draft += 1
    if (isFailing(workflow)) out.failing += 1
  }
  return out
}

export function matchesSegment(workflow: FleetWorkflow, segment: WorkflowSegment): boolean {
  if (segment === "all") return true
  if (segment === "failing") return isFailing(workflow)
  return workflow.status === segment
}

export function filterWorkflows(
  workflows: FleetWorkflow[],
  { query, segment, department, runningOnly = false }: { query: string; segment: WorkflowSegment; department: string; runningOnly?: boolean },
): FleetWorkflow[] {
  const q = query.trim().toLowerCase()
  return workflows.filter((workflow) => {
    if (!matchesSegment(workflow, segment)) return false
    if (runningOnly && !workflow.isRunning) return false
    if (department !== "all" && !workflow.departments.includes(department)) return false
    if (!q) return true
    return [workflow.name, workflow.description, ...workflow.departments, ...workflow.steps].join(" ").toLowerCase().includes(q)
  })
}

export function sortWorkflows(workflows: FleetWorkflow[], sort: WorkflowSort): FleetWorkflow[] {
  const rows = [...workflows]
  switch (sort) {
    case "name":
      return rows.sort((a, b) => a.name.localeCompare(b.name))
    case "success":
      return rows.sort((a, b) => (b.successRate ?? -1) - (a.successRate ?? -1) || a.name.localeCompare(b.name))
    case "runs":
      return rows.sort((a, b) => b.runCount - a.runCount || a.name.localeCompare(b.name))
    default:
      // Running first, then most recently run; never-run workflows last.
      return rows.sort(
        (a, b) =>
          Number(b.isRunning) - Number(a.isRunning) ||
          (b.lastRun ?? "").localeCompare(a.lastRun ?? "") ||
          a.name.localeCompare(b.name),
      )
  }
}

export function runTone(status: string): "ok" | "fail" | "live" | "other" {
  const value = status.toLowerCase()
  if (value === "completed") return "ok"
  if (value === "failed" || value === "rejected" || value === "cancelled") return "fail"
  if (value === "running") return "live"
  return "other"
}

export function successTone(rate: number | null): "" | "warn" | "bad" {
  if (rate === null) return ""
  if (rate < 50) return "bad"
  if (rate < 85) return "warn"
  return ""
}

/** ISO day (YYYY-MM-DD) in the viewer's time zone, or "Never". */
export function lastRunDay(iso: string | null): string {
  if (!iso) return "Never"
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return "Never"
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

export const STATE_LABEL: Record<WorkflowState, string> = {
  active: "Active",
  paused: "Paused",
  draft: "Draft",
  error: "Failing",
}
