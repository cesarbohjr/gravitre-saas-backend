"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { GravitreAgentCard } from "./gravitre-agent-card"
import {
  NodusDepartmentHub,
  NodusSweepConnector,
  sweepAccentForIndex,
} from "./nodus-fleet-chrome"
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
  /**
   * When false (any filter active), only departments with matching agents render —
   * no empty "Drop an agent…" lanes.
   */
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
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <GravitreAgentCard
            key={agent.id}
            agent={agent}
            selected={selectedId === agent.id}
            onSelect={onSelect}
            draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
            nodusGlow
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
        No agents match the current filters.
      </p>
    )
  }

  return (
    <div className="space-y-10">
      {groups.map(({ department, agents: rows }, deptIndex) => {
        const label = DEPARTMENT_ACCENT[department].label
        const accent = sweepAccentForIndex(deptIndex)
        return (
          <DepartmentDropZone
            key={department}
            department={department}
            onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
            className="space-y-4 p-1"
          >
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
              <NodusDepartmentHub label={label} count={rows.length} className="lg:sticky lg:top-2" />

              {rows.length === 0 ? (
                <>
                  <div className="hidden w-10 shrink-0 lg:block xl:w-16">
                    <NodusSweepConnector accent={accent} />
                  </div>
                  <p className="flex-1 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-white/80 px-3 py-8 text-center text-xs text-[color:var(--g-text-muted)] shadow-sm">
                    Drop an agent into {label}
                  </p>
                </>
              ) : (
                <div className="flex min-w-0 flex-1 flex-col gap-3">
                  {rows.map((agent, agentIndex) => (
                    <div
                      key={agent.id}
                      className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3"
                    >
                      <NodusSweepConnector
                        accent={sweepAccentForIndex(deptIndex + agentIndex)}
                        className="max-w-full sm:max-w-[5rem] sm:flex-none xl:max-w-[7rem]"
                      />
                      <div className="min-w-0 flex-1 sm:max-w-xl">
                        <GravitreAgentCard
                          agent={agent}
                          selected={selectedId === agent.id}
                          onSelect={onSelect}
                          draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
                          nodusGlow
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </DepartmentDropZone>
        )
      })}
    </div>
  )
}
