"use client"

import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { GravitreAgentCard } from "./gravitre-agent-card"
import type { AgentDepartmentId, FleetAgent } from "./types"

function groupByDepartment(agents: FleetAgent[]) {
  const order: AgentDepartmentId[] = [
    "sales",
    "customer_success",
    "finance",
    "operations",
    "engineering",
    "marketing",
    "security",
    "general",
  ]
  const map = new Map<AgentDepartmentId, FleetAgent[]>()
  for (const a of agents) {
    const list = map.get(a.department) ?? []
    list.push(a)
    map.set(a.department, list)
  }
  return order.filter((d) => map.has(d)).map((d) => ({ department: d, agents: map.get(d)! }))
}

export function TeamView({
  agents,
  selectedId,
  onSelect,
  grouped = true,
}: {
  agents: FleetAgent[]
  selectedId?: string | null
  onSelect?: (id: string) => void
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
          />
        ))}
      </div>
    )
  }

  const groups = groupByDepartment(agents)
  return (
    <div className="space-y-8">
      {groups.map(({ department, agents: rows }) => (
        <section key={department} className="space-y-3">
          <div className="flex items-baseline gap-2 border-b border-divide pb-2">
            <h3
              className={`text-xs font-semibold uppercase tracking-wide ${DEPARTMENT_ACCENT[department].accentClass}`}
            >
              {DEPARTMENT_ACCENT[department].label}
            </h3>
            <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
              {rows.length}
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {rows.map((agent) => (
              <GravitreAgentCard
                key={agent.id}
                agent={agent}
                selected={selectedId === agent.id}
                onSelect={onSelect}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
