"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone, DepartmentLaneHeader } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { GravitreAgentCard } from "./gravitre-agent-card"
import type { AgentDepartmentId, FleetAgent } from "./types"

function groupByDepartment(agents: FleetAgent[]) {
  const map = new Map<AgentDepartmentId, FleetAgent[]>()
  for (const a of agents) {
    const list = map.get(a.department) ?? []
    list.push(a)
    map.set(a.department, list)
  }
  return FLEET_DEPARTMENT_ORDER.map((d) => ({
    department: d,
    agents: map.get(d) ?? [],
  }))
}

export function TeamView({
  agents,
  selectedId,
  onSelect,
  onDepartmentChange,
  grouped = true,
}: {
  agents: FleetAgent[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  /** Move agent into a department team (persisted by parent). */
  onDepartmentChange?: (agentId: string, department: AgentDepartmentId) => void
  grouped?: boolean
}) {
  if (!grouped) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <GravitreAgentCard
            key={agent.id}
            agent={agent}
            selected={selectedId === agent.id}
            onSelect={onSelect}
            draggable={Boolean(onDepartmentChange)}
          />
        ))}
      </div>
    )
  }

  const groups = groupByDepartment(agents).filter(
    (g) => g.agents.length > 0 || Boolean(onDepartmentChange),
  )

  return (
    <div className="space-y-8">
      {groups.map(({ department, agents: rows }) => (
        <DepartmentDropZone
          key={department}
          department={department}
          onDropAgent={onDepartmentChange}
          className="space-y-3 p-1"
        >
          <DepartmentLaneHeader department={department} count={rows.length} />
          {rows.length === 0 ? (
            <p className="rounded-[var(--np-radius-md)] border border-dashed border-divide bg-white/70 px-3 py-6 text-center text-xs text-[color:var(--g-text-muted)]">
              Drop an agent into {DEPARTMENT_ACCENT[department].label}
            </p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {rows.map((agent) => (
                <GravitreAgentCard
                  key={agent.id}
                  agent={agent}
                  selected={selectedId === agent.id}
                  onSelect={onSelect}
                  draggable={Boolean(onDepartmentChange)}
                />
              ))}
            </div>
          )}
        </DepartmentDropZone>
      ))}
    </div>
  )
}
