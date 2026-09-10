"use client"

import type { DragEvent } from "react"
import { cn } from "@/lib/utils"
import { setFleetAgentDragData } from "./fleet-department-dnd"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import { NodusGlowFrame } from "./nodus-fleet-chrome"
import type { FleetAgent } from "./types"

export function GravitreAgentCard({
  agent,
  selected,
  onSelect,
  draggable = false,
  /** Nodus Aceternity glow frame (TEAM topology). */
  nodusGlow = false,
  /** Dense TEAM canvas card — less chrome, more cards fit. */
  compact = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
  draggable?: boolean
  nodusGlow?: boolean
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

  const inner = (
    <button
      type="button"
      data-fleet-interactive=""
      onClick={() => onSelect?.(agent.id)}
      draggable={draggable}
      onDragStart={onDragStart}
      className={cn(
        "group w-full text-left transition-[border-color,box-shadow]",
        compact ? "p-2" : "p-3",
        nodusGlow
          ? "rounded-[calc(var(--np-radius-md,8px)-1px)] bg-transparent"
          : "rounded-[var(--np-radius-md)] border border-divide bg-white shadow-[var(--np-shadow)] hover:border-[color:var(--g-brand-border)]",
        !nodusGlow && selected && "border-[color:var(--g-brand)]/50 ring-2 ring-[color:var(--g-brand)]/40",
        nodusGlow && selected && "ring-2 ring-[color:var(--g-brand)]/45 ring-offset-1",
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
          {!compact && agent.currentActivity ? (
            <p className="mt-2 truncate text-xs text-[color:var(--g-text-primary)]">
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
              ) : null}
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

  if (!nodusGlow) return inner

  return (
    <NodusGlowFrame
      className={cn("w-full shadow-md", compact && "max-w-[200px]")}
      contentClassName="bg-white dark:bg-neutral-900"
      size={compact ? "sm" : "md"}
    >
      {inner}
    </NodusGlowFrame>
  )
}
