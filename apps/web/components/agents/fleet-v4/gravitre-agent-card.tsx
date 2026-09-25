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
      data-agent-id={agent.id}
      onClick={() => onSelect?.(agent.id)}
      draggable={draggable}
      onDragStart={onDragStart}
      className={cn(
        "group w-full rounded-[var(--np-radius-md)] border text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        compact ? "px-2.5 py-2" : "p-3",
        selected
          ? "border-[color:var(--g-border-strong)] bg-[color:var(--g-surface-1)] shadow-[inset_2px_0_0_0_var(--g-brand)]"
          : "border-transparent hover:border-[color:var(--g-border-default)] hover:bg-[color:var(--g-surface-1)]",
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
                  compact ? "text-[13px] leading-snug" : "text-sm",
                )}
              >
                {agent.name}
              </p>
              <p className="truncate text-xs text-[color:var(--g-text-muted)]">
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
            ) : agent.tasksToday > 0 ? (
              <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                {agent.tasksToday} today
              </span>
            ) : null}
          </div>
          {agent.currentActivity ? (
            <p
              className={cn(
                "truncate text-[color:var(--g-text-primary)]",
                compact ? "mt-1 text-[11px]" : "mt-2 text-xs",
              )}
            >
              {agent.currentActivity}
            </p>
          ) : null}
          {!compact ? (
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-[11px] font-medium text-[color:var(--g-text-secondary)]">
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
          ) : null}
        </div>
      </div>
    </button>
  )
}
