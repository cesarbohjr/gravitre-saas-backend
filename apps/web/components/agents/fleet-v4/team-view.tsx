"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { DepartmentDropZone } from "./department-drop-zone"
import { FLEET_DEPARTMENT_ORDER } from "./fleet-department-dnd"
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
 * Multiple departments converge into one Gravitre hub (template-preview layout).
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

  const filled = groups.filter((g) => g.agents.length > 0)
  const empty = groups.filter((g) => g.agents.length === 0)

  return (
    <div className="space-y-8">
      {/* Primary Nodus canvas: departments → Gravitre → agents */}
      {filled.length > 0 ? (
        <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:gap-2 xl:gap-4">
          {/* Left: department icon + label rails */}
          <div className="flex w-full shrink-0 flex-col justify-center gap-8 lg:w-[11.5rem] xl:w-52">
            {filled.map(({ department, agents: rows }, i) => {
              const label = DEPARTMENT_ACCENT[department].label
              const accent = sweepAccentForIndex(i)
              const variant = convergeVariantForIndex(i, filled.length)
              return (
                <DepartmentDropZone
                  key={department}
                  department={department}
                  onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
                  className="relative"
                >
                  <div className="flex items-center gap-0">
                    <NodusDepartmentLabel
                      department={department}
                      label={label}
                      count={rows.length}
                      className="min-w-0 flex-1"
                    />
                    <div className="hidden lg:block">
                      <NodusConvergeConnector variant={variant} accent={accent} />
                    </div>
                  </div>
                </DepartmentDropZone>
              )
            })}
          </div>

          {/* Center: Gravitre logo hub */}
          <div className="flex shrink-0 flex-col items-center gap-2 self-center">
            <div className="flex w-full max-w-[6rem] items-center lg:hidden">
              <NodusSweepConnector accent="blue" />
            </div>
            <NodusGravitreHub />
            <div className="flex w-full max-w-[6rem] items-center lg:hidden">
              <NodusSweepConnector accent="coral" />
            </div>
          </div>

          {/* Outbound sweep into agents */}
          <div className="hidden w-10 shrink-0 lg:block xl:w-14">
            <NodusSweepConnector accent="blue" />
          </div>

          {/* Right: agent cards */}
          <div className="grid min-w-0 flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {filled.flatMap(({ department, agents: rows }) =>
              rows.map((agent) => (
                <DepartmentDropZone
                  key={agent.id}
                  department={department}
                  onDropAgent={showEmptyDepartments ? onDepartmentChange : undefined}
                  className="min-w-0"
                >
                  <GravitreAgentCard
                    agent={agent}
                    selected={selectedId === agent.id}
                    onSelect={onSelect}
                    draggable={Boolean(onDepartmentChange) && showEmptyDepartments}
                    nodusGlow
                  />
                </DepartmentDropZone>
              )),
            )}
          </div>
        </div>
      ) : null}

      {/* Empty department drop lanes — only when filters are All */}
      {empty.length > 0 ? (
        <div className="space-y-3 border-t border-divide pt-6">
          <p className="text-[11px] text-[color:var(--g-text-muted)]">
            Drop agents into an empty department
          </p>
          <div className="flex flex-wrap gap-3">
            {empty.map(({ department }, i) => {
              const label = DEPARTMENT_ACCENT[department].label
              return (
                <DepartmentDropZone
                  key={department}
                  department={department}
                  onDropAgent={onDepartmentChange}
                  className="min-w-[12rem] flex-1 border border-dashed border-divide bg-white/80 px-3 py-4 sm:flex-none"
                >
                  <div className="flex items-center gap-3">
                    <NodusDepartmentLabel department={department} label={label} count={0} />
                    <NodusSweepConnector
                      accent={sweepAccentForIndex(i)}
                      className="max-w-[3rem]"
                    />
                    <NodusGravitreHub className="h-10 w-10 sm:h-10 sm:w-10" />
                  </div>
                  <p className="mt-2 text-center text-[10px] text-[color:var(--g-text-muted)]">
                    Drop here
                  </p>
                </DepartmentDropZone>
              )
            })}
          </div>
        </div>
      ) : null}
    </div>
  )
}
