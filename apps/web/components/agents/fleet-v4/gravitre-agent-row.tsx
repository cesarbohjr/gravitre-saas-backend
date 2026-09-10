"use client"

import type { DragEvent, MouseEvent } from "react"
import { cn } from "@/lib/utils"
import { DEPARTMENT_ACCENT } from "./identity-tokens"
import { FLEET_DEPARTMENT_ORDER, setFleetAgentDragData } from "./fleet-department-dnd"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { AgentDepartmentId, FleetAgent } from "./types"

export function GravitreAgentRow({
  agent,
  selected,
  onSelect,
  onDepartmentChange,
  draggable = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
  onDepartmentChange?: (agentId: string, department: AgentDepartmentId) => void
  draggable?: boolean
  className?: string
}) {
  const onDragStart = (e: DragEvent) => {
    if (!draggable) return
    setFleetAgentDragData(e.dataTransfer, {
      agentId: agent.id,
      fromDepartment: agent.department,
    })
  }

  return (
    <tr
      className={cn(
        "cursor-pointer transition-colors hover:bg-[color:var(--g-surface-2)]/50",
        selected && "bg-[color:var(--g-brand-soft)]/35",
        draggable && "cursor-grab active:cursor-grabbing",
        className,
      )}
      onClick={() => onSelect?.(agent.id)}
      draggable={draggable}
      onDragStart={onDragStart}
    >
      <td className="h-12 border-b border-divide/70 px-4">
        <div className="flex min-w-[200px] items-center gap-2.5">
          <GravitreAgentIdentity
            icon={agent.icon}
            identityColor={agent.identityColor}
            status={agent.runtimeState}
            variant="row"
          />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[color:var(--g-text-primary)]">
              {agent.name}
            </p>
            <p className="truncate text-xs text-[color:var(--g-text-muted)]">{agent.role}</p>
          </div>
        </div>
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-sm text-[color:var(--g-text-muted)]">
        {onDepartmentChange ? (
          <select
            aria-label={`Department for ${agent.name}`}
            value={agent.department}
            onClick={(event: MouseEvent) => event.stopPropagation()}
            onChange={(event) => {
              event.stopPropagation()
              const next = event.target.value as AgentDepartmentId
              if (next === agent.department) return
              onDepartmentChange(agent.id, next)
            }}
            className="max-w-[11rem] rounded-md border border-divide bg-white px-2 py-1 text-xs text-[color:var(--g-text-primary)] focus:outline-none focus:ring-1 focus:ring-[color:var(--g-brand)]"
          >
            {FLEET_DEPARTMENT_ORDER.map((department) => (
              <option key={department} value={department}>
                {DEPARTMENT_ACCENT[department].label}
              </option>
            ))}
          </select>
        ) : (
          agent.departmentLabel
        )}
      </td>
      <td className="h-12 border-b border-divide/70 px-4">
        <GravitreAgentStatus runtimeState={agent.runtimeState} configState={agent.configState} showConfig />
      </td>
      <td className="h-12 border-b border-divide/70 px-4">
        <div className="flex max-w-[220px] items-center gap-2">
          <span className="truncate text-sm text-[color:var(--g-text-primary)]">
            {agent.currentActivity ?? "—"}
          </span>
          <GravitreAgentActivityIndicator runtimeState={agent.runtimeState} />
        </div>
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-sm tabular-nums text-[color:var(--g-text-muted)]">
        {agent.tasksToday}
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-sm tabular-nums text-[color:var(--g-text-muted)]">
        {agent.successRate != null ? `${agent.successRate}%` : "—"}
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-sm text-[color:var(--g-text-muted)]">
        {agent.model}
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-sm text-[color:var(--g-text-muted)]">
        {agent.lastActiveLabel}
      </td>
      <td className="h-12 border-b border-divide/70 px-4 text-right text-xs font-medium text-[color:var(--g-brand)]">
        Open
      </td>
    </tr>
  )
}
