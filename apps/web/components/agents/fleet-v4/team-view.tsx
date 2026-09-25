"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { GravitreAgentCard } from "./gravitre-agent-card"
import { NodusDepartmentLabel } from "./nodus-fleet-chrome"
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

/**
 * Operating team: coworkers grouped by department and function.
 * One Intelligence Core — no hub glow, no separate AI faces.
 */
export function TeamView({
  agents,
  selectedId,
  onSelect,
  onDepartmentChange,
  grouped = true,
  showEmptyDepartments = true,
}: {
  agents: FleetAgent[]
  selectedId?: string | null
  onSelect?: (id: string) => void
  onDepartmentChange?: (agentId: string, department: AgentDepartmentId) => void
  grouped?: boolean
  showEmptyDepartments?: boolean
}) {
  if (!grouped) {
    return (
      <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
        {agents.map((agent) => (
          <GravitreAgentCard
            key={agent.id}
            agent={agent}
            selected={selectedId === agent.id}
            onSelect={onSelect}
            draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
            compact
          />
        ))}
      </div>
    )
  }

  const groups = groupByDepartment(agents).filter((g) => {
    if (g.agents.length > 0) return true
    return showEmptyDepartments && Boolean(onDepartmentChange)
  })

  if (groups.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-[color:var(--g-text-muted)]">
        No teammates match the current filters.
      </p>
    )
  }

  const filled = groups.filter((g) => g.agents.length > 0)
  const empty = groups.filter((g) => g.agents.length === 0)

  return (
    <div className="space-y-6">
      {filled.map(({ department, agents: rows }) => (
        <section key={department} aria-label={DEPARTMENT_ACCENT[department].label}>
          <DepartmentDropZone
            department={department}
            onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
            className="rounded-md"
          >
            <NodusDepartmentLabel
              department={department}
              label={DEPARTMENT_ACCENT[department].label}
              count={rows.length}
            />
            <div className="mt-2 grid gap-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {rows.map((agent) => (
                <GravitreAgentCard
                  key={agent.id}
                  agent={agent}
                  selected={selectedId === agent.id}
                  onSelect={onSelect}
                  draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
                  compact
                />
              ))}
            </div>
          </DepartmentDropZone>
        </section>
      ))}

      {empty.length > 0 ? (
        <div className="space-y-2 border-t border-[color:var(--g-border-subtle)] pt-5">
          <p className="text-xs text-[color:var(--g-text-muted)]">
            Empty departments. Drag a teammate here to reassign.
          </p>
          <div className="flex flex-wrap gap-2">
            {empty.map(({ department }) => {
              const label = DEPARTMENT_ACCENT[department].label
              return (
                <DepartmentDropZone
                  key={department}
                  department={department}
                  onDropAgent={onDepartmentChange}
                  className="min-w-[12rem] flex-1 rounded-[var(--np-radius-md)] border border-dashed border-[color:var(--g-border-default)] px-3 py-2.5 sm:flex-none"
                >
                  <NodusDepartmentLabel department={department} label={label} count={0} />
                </DepartmentDropZone>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
