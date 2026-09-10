"use client"

import type { DragEvent } from "react"
import { cn } from "@/lib/utils"
import { setFleetAgentDragData } from "./fleet-department-dnd"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentDepartmentBadge } from "./gravitre-agent-department-badge"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import type { FleetAgent } from "./types"

/** Graph node — Nodus white tile + dept + status (Relationships language). */
export function GravitreAgentNode({
  agent,
  selected,
  executing,
  onSelect,
  draggable = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  executing?: boolean
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
    <button
      type="button"
      onClick={() => onSelect?.(agent.id)}
      draggable={draggable}
      onDragStart={onDragStart}
      className={cn(
        "w-[188px] rounded-[var(--np-radius-md)] border border-divide bg-white px-3 py-2 text-left shadow-[var(--np-shadow)] transition-shadow",
        selected && "ring-2 ring-[color:var(--g-brand)]/55",
        executing && "border-[color:var(--g-brand)]/45",
        draggable && "cursor-grab active:cursor-grabbing",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <GravitreAgentIdentity
          icon={agent.icon}
          identityColor={agent.identityColor}
          status={agent.runtimeState}
          variant="graph"
        />
        <div className="min-w-0 flex-1">
          <GravitreAgentDepartmentBadge department={agent.department} className="block" />
          <p className="truncate text-sm font-medium text-[color:var(--g-text-primary)]">{agent.name}</p>
          <div className="mt-1 flex items-center gap-1.5">
            {executing || agent.currentActivity ? (
              <>
                <GravitreAgentActivityIndicator runtimeState={agent.runtimeState} />
                <span className="truncate text-[10px] text-[color:var(--g-text-muted)]">
                  {agent.currentActivity ?? "Working"}
                </span>
              </>
            ) : (
              <span className="text-[10px] text-[color:var(--g-text-muted)]">{agent.role}</span>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}
