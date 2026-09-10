/**
 * Agents fleet UI preferences (Agents 4.0 Phase 3).
 * Persists to user_ui_preferences.agentsFleet when available;
 * always mirrors localStorage as immediate + offline fallback.
 */

export type AgentsFleetViewPref = "team" | "list" | "graph"

export type AgentsFleetSortId =
  | "name"
  | "department"
  | "status"
  | "tasks_today"
  | "success_rate"
  | "last_active"

export type AgentsFleetFilters = {
  department: string | null
  status: string | null
  role: string | null
  model: string | null
}

export type AgentsFleetPrefs = {
  version: 1
  view: AgentsFleetViewPref
  sort: AgentsFleetSortId
  sortDir: "asc" | "desc"
  filters: AgentsFleetFilters
  updatedAt?: string
}

export const DEFAULT_AGENTS_FLEET_PREFS: AgentsFleetPrefs = {
  version: 1,
  view: "team",
  sort: "name",
  sortDir: "asc",
  filters: {
    department: null,
    status: null,
    role: null,
    model: null,
  },
}

export const AGENTS_FLEET_STORAGE_KEY = "gravitre:agentsFleet:v1"

export function isAgentsFleetView(value: unknown): value is AgentsFleetViewPref {
  return value === "team" || value === "list" || value === "graph"
}

export function isAgentsFleetSort(value: unknown): value is AgentsFleetSortId {
  return (
    value === "name" ||
    value === "department" ||
    value === "status" ||
    value === "tasks_today" ||
    value === "success_rate" ||
    value === "last_active"
  )
}

export function normalizeAgentsFleetPrefs(raw: unknown): AgentsFleetPrefs {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_AGENTS_FLEET_PREFS }
  const o = raw as Record<string, unknown>
  const filtersRaw = (o.filters && typeof o.filters === "object" ? o.filters : {}) as Record<
    string,
    unknown
  >
  return {
    version: 1,
    view: isAgentsFleetView(o.view) ? o.view : DEFAULT_AGENTS_FLEET_PREFS.view,
    sort: isAgentsFleetSort(o.sort) ? o.sort : DEFAULT_AGENTS_FLEET_PREFS.sort,
    sortDir: o.sortDir === "desc" ? "desc" : "asc",
    filters: {
      department: typeof filtersRaw.department === "string" ? filtersRaw.department : null,
      status: typeof filtersRaw.status === "string" ? filtersRaw.status : null,
      role: typeof filtersRaw.role === "string" ? filtersRaw.role : null,
      model: typeof filtersRaw.model === "string" ? filtersRaw.model : null,
    },
    updatedAt: typeof o.updatedAt === "string" ? o.updatedAt : undefined,
  }
}

export function readLocalAgentsFleetPrefs(): AgentsFleetPrefs | null {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(AGENTS_FLEET_STORAGE_KEY)
    if (!raw) return null
    return normalizeAgentsFleetPrefs(JSON.parse(raw))
  } catch {
    return null
  }
}

export function writeLocalAgentsFleetPrefs(prefs: AgentsFleetPrefs): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      AGENTS_FLEET_STORAGE_KEY,
      JSON.stringify({ ...prefs, updatedAt: new Date().toISOString() }),
    )
  } catch {
    // quota / private mode
  }
}

export async function fetchRemoteAgentsFleetPrefs(): Promise<AgentsFleetPrefs | null> {
  try {
    const res = await fetch("/api/settings/agents-fleet", { credentials: "include" })
    if (!res.ok) return null
    const body = (await res.json()) as { prefs?: unknown }
    if (!body.prefs) return null
    return normalizeAgentsFleetPrefs(body.prefs)
  } catch {
    return null
  }
}

export async function saveRemoteAgentsFleetPrefs(prefs: AgentsFleetPrefs): Promise<boolean> {
  try {
    const res = await fetch("/api/settings/agents-fleet", {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prefs }),
    })
    return res.ok
  } catch {
    return false
  }
}
