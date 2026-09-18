"use client"

import type { DragEvent } from "react"
import { cn } from "@/lib/utils"
import { setFleetAgentDragData } from "./fleet-department-dnd"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { FleetAgent } from "./types"

export function GravitreAgentCard({
  agent,
  selected,
  onSelect,
  draggable = false,
  compact = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
  draggable?: boolean
  compact?: boolean
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
      data-fleet-interactive=""
      onClick={() => onSelect?.(agent.id)}
      draggable={draggable}
      onDragStart={onDragStart}
      className={cn(
        "group w-full rounded-[var(--np-radius-md)] border border-divide bg-white text-left shadow-[var(--np-shadow)] transition-[border-color,box-shadow] hover:border-[color:var(--g-brand-border)]",
        compact ? "p-2" : "p-3",
        selected && "border-[color:var(--g-brand)]/50 ring-2 ring-[color:var(--g-brand)]/40",
        draggable && "cursor-grab active:cursor-grabbing",
        className,
      )}
    >
      <div className={cn("flex items-start", compact ? "gap-2" : "gap-3")}>
        <GravitreAgentIdentity
          icon={agent.icon}
          identityColor={agent.identityColor}
          status={agent.runtimeState}
          variant={compact ? "graph" : "card"}
          size={compact ? "sm" : undefined}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-1.5">
            <div className="min-w-0">
              <p
                className={cn(
                  "truncate font-medium text-[color:var(--g-text-primary)]",
                  compact ? "text-xs leading-snug" : "text-sm",
                )}
              >
                {agent.name}
              </p>
              <p className="truncate text-[10px] text-[color:var(--g-text-muted)] sm:text-xs">
                {agent.role}
              </p>
            </div>
            {!compact ? (
              <GravitreAgentActivityIndicator runtimeState={agent.runtimeState} />
            ) : null}
          </div>
          <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-0.5", compact ? "mt-1" : "mt-2")}>
            <GravitreAgentStatus
              runtimeState={agent.runtimeState}
              configState={agent.configState}
              showConfig={!compact}
            />
            {!compact ? (
              <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                {agent.tasksToday} tasks today
              </span>
            ) : (
              <span className="text-[10px] tabular-nums text-[color:var(--g-text-muted)]">
                {agent.tasksToday} today
              </span>
            )}
          </div>
          {agent.currentActivity ? (
            <p
              className={cn(
                "truncate text-[color:var(--g-text-primary)]",
                compact ? "mt-1 text-[10px]" : "mt-2 text-xs",
              )}
            >
              {agent.currentActivity}
            </p>
          ) : null}
          {!compact ? (
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-brand)]">
                {agent.departmentLabel}
              </span>
              {agent.successRate != null ? (
                <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                  {agent.successRate}% · {agent.lastActiveLabel}
                </span>
              ) : (
                <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                  {agent.lastActiveLabel}
                </span>
              )}
            </div>
          ) : (
            <p className="mt-1 text-[9px] font-medium uppercase tracking-wide text-[color:var(--g-brand)]">
              {agent.departmentLabel}
            </p>
          )}
        </div>
      </div>
    </button>
  )
}
