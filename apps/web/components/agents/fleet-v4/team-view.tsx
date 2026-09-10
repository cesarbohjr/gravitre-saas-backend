"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
import { FleetPanCanvas } from "./fleet-pan-canvas"
import { GravitreAgentCard } from "./gravitre-agent-card"
import {
  NodusConvergeConnector,
  NodusDepartmentLabel,
  NodusGravitreHub,
  NodusSweepConnector,
  convergeVariantForIndex,
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

/**
 * Nodus topology:
 *   [dept icon + label] ──sweep──▶ [Gravitre logo] ──sweep──▶ [agent cards]
 * Pannable canvas so operators can drag agents into department drop targets.
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
            nodusGlow
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
        No agents match the current filters.
      </p>
    )
  }

  const filled = groups.filter((g) => g.agents.length > 0)
  const empty = groups.filter((g) => g.agents.length === 0)

  return (
    <FleetPanCanvas>
      <div className="space-y-8">
        {filled.length > 0 ? (
          <div className="flex flex-row items-center gap-3 xl:gap-5">
            {/* Left: full department labels (no truncation) */}
            <div className="flex w-[13.5rem] shrink-0 flex-col justify-center gap-7 xl:w-[15rem]">
              {filled.map(({ department, agents: rows }, i) => {
                const label = DEPARTMENT_ACCENT[department].label
                const accent = sweepAccentForIndex(i)
                const variant = convergeVariantForIndex(i, filled.length)
                return (
                  <DepartmentDropZone
                    key={department}
                    department={department}
                    onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
                    className="relative rounded-md px-1 py-1"
                  >
                    <div className="flex items-center gap-1">
                      <NodusDepartmentLabel
                        department={department}
                        label={label}
                        count={rows.length}
                        className="shrink-0"
                      />
                      <div className="hidden min-w-[4.5rem] flex-1 sm:block xl:min-w-[6rem]">
                        <NodusConvergeConnector variant={variant} accent={accent} />
                      </div>
                    </div>
                  </DepartmentDropZone>
                )
              })}
            </div>

            <div className="flex shrink-0 flex-col items-center self-center">
              <NodusGravitreHub className="h-12 w-12 sm:h-14 sm:w-14" />
            </div>

            <div className="hidden w-8 shrink-0 sm:block xl:w-12">
              <NodusSweepConnector accent="blue" />
            </div>

            {/* Right: compact agent cards */}
            <div className="grid min-w-0 flex-1 grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5">
              {filled.flatMap(({ department, agents: rows }) =>
                rows.map((agent) => (
                  <DepartmentDropZone
                    key={agent.id}
                    department={department}
                    onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
                    className="min-w-0 max-w-[200px]"
                  >
                    <GravitreAgentCard
                      agent={agent}
                      selected={selectedId === agent.id}
                      onSelect={onSelect}
                      draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
                      nodusGlow
                      compact
                    />
                  </DepartmentDropZone>
                )),
              )}
            </div>
          </div>
        ) : null}

        {empty.length > 0 ? (
          <div className="space-y-3 border-t border-divide pt-6">
            <p className="text-[11px] text-[color:var(--g-text-muted)]">
              Drop agents into an empty department — pan the canvas to reach every lane
            </p>
            <div className="flex flex-wrap gap-3">
              {empty.map(({ department }, i) => {
                const label = DEPARTMENT_ACCENT[department].label
                return (
                  <DepartmentDropZone
                    key={department}
                    department={department}
                    onDropAgent={onDepartmentChange}
                    className="min-h-[5.5rem] min-w-[16rem] flex-1 border border-dashed border-divide bg-white/90 px-4 py-4 sm:flex-none"
                  >
                    <div className="flex items-center gap-3">
                      <NodusDepartmentLabel department={department} label={label} count={0} />
                      <NodusSweepConnector
                        accent={sweepAccentForIndex(i)}
                        className="max-w-[2.5rem]"
                      />
                    </div>
                    <p className="mt-2 text-[10px] text-[color:var(--g-text-muted)]">Drop here</p>
                  </DepartmentDropZone>
                )
              })}
            </div>
          </div>
        ) : null}
      </div>
    </FleetPanCanvas>
  )
}
