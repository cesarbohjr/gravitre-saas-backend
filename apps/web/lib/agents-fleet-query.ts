import type { FleetAgent } from "@/components/agents/fleet-v4/types"
import type { AgentsFleetFilters, AgentsFleetSortId } from "@/lib/agents-fleet-prefs"

const STATUS_ORDER: Record<string, number> = {
  executing: 0,
  thinking: 1,
  retrieving: 2,
  planning: 3,
  delegating: 4,
  waiting_approval: 5,
  available: 6,
  idle: 7,
  completed: 8,
  blocked: 9,
  failed: 10,
  offline: 11,
}

function parseLastActiveMs(label: string): number {
  const t = Date.parse(label)
  if (!Number.isNaN(t)) return t
  // Relative labels ("4m ago") — keep stable order by string only.
  return 0
}

export function filterFleetAgents(
  agents: FleetAgent[],
  filters: AgentsFleetFilters,
): FleetAgent[] {
  return agents.filter((agent) => {
    if (filters.department) {
      const d = filters.department.trim().toLowerCase()
      const label = agent.departmentLabel.trim().toLowerCase()
      const id = agent.department.trim().toLowerCase()
      if (label !== d && id !== d) {
        return false
      }
    }
    if (filters.status && agent.runtimeState !== filters.status) return false
    if (filters.role && agent.role !== filters.role) return false
    if (filters.model && agent.model !== filters.model) return false
    return true
  })
}

export function sortFleetAgents(
  agents: FleetAgent[],
  sort: AgentsFleetSortId,
  sortDir: "asc" | "desc",
): FleetAgent[] {
  const dir = sortDir === "desc" ? -1 : 1
  const copy = [...agents]
  copy.sort((a, b) => {
    let cmp = 0
    switch (sort) {
      case "name":
        cmp = a.name.localeCompare(b.name)
        break
      case "department":
        cmp = a.departmentLabel.localeCompare(b.departmentLabel) || a.name.localeCompare(b.name)
        break
      case "status":
        cmp =
          (STATUS_ORDER[a.runtimeState] ?? 99) - (STATUS_ORDER[b.runtimeState] ?? 99) ||
          a.name.localeCompare(b.name)
        break
      case "tasks_today":
        cmp = a.tasksToday - b.tasksToday
        break
      case "success_rate": {
        const ar = a.successRate ?? -1
        const br = b.successRate ?? -1
        cmp = ar - br
        break
      }
      case "last_active":
        cmp = parseLastActiveMs(a.lastActiveLabel) - parseLastActiveMs(b.lastActiveLabel)
        if (cmp === 0) cmp = a.lastActiveLabel.localeCompare(b.lastActiveLabel)
        break
      default:
        cmp = a.name.localeCompare(b.name)
    }
    return cmp * dir
  })
  return copy
}

export function uniqueSorted(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b))
}
