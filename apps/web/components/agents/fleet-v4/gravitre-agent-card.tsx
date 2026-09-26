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
  surface = false,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
  draggable?: boolean
  compact?: boolean
  /** Workforce card on a department lane: raised surface, identity-first. */
  surface?: boolean
  className?: string
}) {
  const onDragStart = (e: DragEvent) => {
    if (!draggable) return
    setFleetAgentDragData(e.dataTransfer, {
      agentId: agent.id,
      fromDepartment: agent.department,
    })
  }

  if (surface) {
    return (
      <button
        type="button"
        data-fleet-interactive=""
        data-agent-id={agent.id}
        onClick={() => onSelect?.(agent.id)}
        draggable={draggable}
        onDragStart={onDragStart}
        aria-pressed={selected}
        className={cn(
          "group flex h-full w-full flex-col rounded-[12px] border bg-card p-3 text-left transition-[border-color,box-shadow] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          selected
            ? "border-[color:var(--g-brand)] shadow-[0_0_0_3px_var(--g-brand-soft)]"
            : "border-[color:var(--g-border-default)] hover:border-[color:var(--g-border-strong)] hover:shadow-sm",
          draggable && "cursor-grab active:cursor-grabbing",
          className,
        )}
      >
        <div className="flex items-start gap-3">
          <GravitreAgentIdentity
            icon={agent.icon}
            identityColor={agent.identityColor}
            status={agent.runtimeState}
            variant="card"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <p className="truncate text-[13.5px] font-semibold leading-snug text-[color:var(--g-text-primary)]">
                {agent.name}
              </p>
              <GravitreAgentActivityIndicator runtimeState={agent.runtimeState} />
            </div>
            <p className="truncate text-xs text-[color:var(--g-text-muted)]">{agent.role}</p>
            <div className="mt-1.5">
              <GravitreAgentStatus runtimeState={agent.runtimeState} configState={agent.configState} showConfig />
            </div>
          </div>
        </div>
        <p
          className={cn(
            "mt-2.5 line-clamp-2 min-h-[2lh] text-xs",
            agent.currentActivity ? "text-[color:var(--g-text-primary)]" : "text-[color:var(--g-text-muted)]",
          )}
        >
          {agent.currentActivity ?? "No active task."}
        </p>
        <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-[color:var(--g-border-subtle)] pt-2 text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
          <span>{agent.tasksToday} tasks today</span>
          <span className="truncate">
            {agent.successRate != null ? `${agent.successRate}% · ` : ""}
            {agent.lastActiveLabel}
          </span>
        </div>
      </button>
    )
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
