/**
 * Lite seats page data: departments summary, members, assignments and the
 * real resource lists Lite users can be given (workflows, agents, knowledge
 * packs). Councils have no list endpoint, so they are assigned by id.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"

export type LiteResourceType = "workflow" | "agent" | "council" | "knowledge_pack"

export const LITE_RESOURCE_TYPES: Array<{ id: LiteResourceType; label: string }> = [
  { id: "workflow", label: "Workflow" },
  { id: "agent", label: "Agent" },
  { id: "council", label: "Council" },
  { id: "knowledge_pack", label: "Knowledge pack" },
]

export interface LiteDepartment {
  id: string
  name: string
  lite_seat_allocation: number
  used_seats: number
  available_seats?: number
  resource_count?: number
  department_admin_id?: string | null
  status?: string
  created_at?: string | null
}

export interface LiteSummary {
  included: number | null
  included_display?: string
  unlimited?: boolean
  allocated: number
  used: number
  plan_code?: string | null
}

export interface LiteSeatsPayload {
  summary?: Partial<LiteSummary>
  departments?: LiteDepartment[]
}

export interface LiteMember {
  id: string
  user_id: string
  role: "admin" | "viewer"
  email?: string | null
  name?: string | null
  created_at?: string | null
}

export interface LiteAssignment {
  id?: string
  department_id: string
  resource_type: LiteResourceType
  resource_id: string
  created_at?: string | null
}

export interface LiteResourceOption {
  id: string
  name: string
}

export const LITE_SEATS_KEY = "/api/settings/lite-seats"
export const membersKey = (departmentId: string) => `/api/departments/${encodeURIComponent(departmentId)}/members`
export const assignmentsKey = (departmentId: string) =>
  `/api/departments/${encodeURIComponent(departmentId)}/assignments`

async function readError(response: Response, fallback: string): Promise<Error> {
  const payload = await response.json().catch(() => ({}))
  return new Error(extractApiErrorMessage(payload) || `${fallback} (${response.status})`)
}

export const liteApi = {
  members: (departmentId: string) => fetcher<{ members: LiteMember[] }>(membersKey(departmentId)),
  assignments: (departmentId: string) => fetcher<{ assignments: LiteAssignment[] }>(assignmentsKey(departmentId)),
  assign: async (departmentId: string, resourceType: LiteResourceType, resourceId: string) => {
    const response = await apiFetch("/api/departments/assignments", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ department_id: departmentId, resource_type: resourceType, resource_id: resourceId }),
    })
    if (!response.ok) throw await readError(response, "Assign failed")
    return (await response.json()) as { assignment: LiteAssignment }
  },
  unassign: async (departmentId: string, resourceType: LiteResourceType, resourceId: string) => {
    const query = new URLSearchParams({ department_id: departmentId, resource_type: resourceType, resource_id: resourceId })
    const response = await apiFetch(`/api/departments/assignments?${query.toString()}`, { method: "DELETE" })
    if (!response.ok) throw await readError(response, "Remove failed")
  },
}

/** Load the pickable resources of one type from the real list endpoints. */
export async function loadResourceOptions(type: LiteResourceType): Promise<LiteResourceOption[]> {
  if (type === "workflow") {
    const data = await fetcher<{ workflows?: Array<{ id: string; name?: string | null }> }>("/api/workflows")
    return toOptions(data.workflows)
  }
  if (type === "agent") {
    const data = await fetcher<{ agents?: Array<{ id: string; name?: string | null }> }>("/api/agents")
    return toOptions(data.agents)
  }
  if (type === "knowledge_pack") {
    const data = await fetcher<{
      installs?: Array<{
        installedEntityId?: string | null
        asset?: { title?: string | null; assetType?: string | null } | null
      }>
    }>("/api/marketplace/installs?status=active&limit=100")
    return knowledgePackOptions(data.installs)
  }
  return []
}

export function toOptions(rows: Array<{ id: string; name?: string | null }> | undefined): LiteResourceOption[] {
  const seen = new Set<string>()
  const out: LiteResourceOption[] = []
  for (const row of rows ?? []) {
    if (!row?.id || seen.has(row.id)) continue
    seen.add(row.id)
    out.push({ id: row.id, name: (row.name || "").trim() || "Untitled" })
  }
  return out.sort((a, b) => a.name.localeCompare(b.name))
}

/** Installed marketplace knowledge packs; the installed entity id is what gets assigned. */
export function knowledgePackOptions(
  installs:
    | Array<{ installedEntityId?: string | null; asset?: { title?: string | null; assetType?: string | null } | null }>
    | undefined,
): LiteResourceOption[] {
  return toOptions(
    (installs ?? [])
      .filter((install) => install.asset?.assetType === "knowledge_pack" && install.installedEntityId)
      .map((install) => ({ id: String(install.installedEntityId), name: install.asset?.title ?? null })),
  )
}

export interface LiteTotals {
  includedLabel: string
  planLabel: string | null
  allocated: number
  departments: number
  used: number
}

const PLAN_NAMES: Record<string, string> = {
  free: "Free",
  node: "Node",
  control: "Control",
  command: "Command",
  enterprise: "Enterprise",
}

export function planLabel(code: string | null | undefined): string | null {
  const key = String(code ?? "").trim().toLowerCase()
  if (!key) return null
  const name = PLAN_NAMES[key] ?? key.charAt(0).toUpperCase() + key.slice(1)
  return `${name} plan`
}

export function liteTotals(payload: LiteSeatsPayload | undefined): LiteTotals {
  const summary = payload?.summary ?? {}
  const departments = payload?.departments ?? []
  const unlimited = summary.unlimited === true || (summary.included === null && summary.unlimited !== false)
  const includedLabel = unlimited
    ? "Unlimited"
    : summary.included_display ?? String(Number(summary.included ?? 0))
  return {
    includedLabel,
    planLabel: planLabel(summary.plan_code),
    allocated:
      typeof summary.allocated === "number"
        ? summary.allocated
        : departments.reduce((sum, d) => sum + Number(d.lite_seat_allocation || 0), 0),
    departments: departments.length,
    used:
      typeof summary.used === "number" ? summary.used : departments.reduce((sum, d) => sum + Number(d.used_seats || 0), 0),
  }
}

/** Usage bar width: at least a sliver when anything is used, 0 when nothing is allocated. */
export function seatBarWidth(used: number, allocated: number): string {
  if (!allocated) return "0%"
  if (!used) return "0%"
  return `${Math.min(100, Math.max(4, Math.round((used / allocated) * 100)))}%`
}

export function filterDepartments(departments: LiteDepartment[], query: string): LiteDepartment[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return departments
  return departments.filter((d) => d.name.toLowerCase().includes(needle))
}

export const LITE_PAGE_SIZE = 10

export function pageSlice<T>(rows: T[], page: number, size = LITE_PAGE_SIZE) {
  const total = rows.length
  const pageCount = Math.max(1, Math.ceil(total / size))
  const current = Math.min(Math.max(1, page), pageCount)
  const start = (current - 1) * size
  return {
    page: current,
    pageCount,
    rows: rows.slice(start, start + size),
    from: total ? start + 1 : 0,
    to: Math.min(start + size, total),
    total,
  }
}
