"use client"

import type { DragEvent } from "react"
import { cn } from "@/lib/utils"
import { setFleetAgentDragData } from "./fleet-department-dnd"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { FleetAgent } from "./types"

export function GravitreAgentRow({
  agent,
  selected,
  onSelect,
  draggable = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
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
        {agent.departmentLabel}
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
