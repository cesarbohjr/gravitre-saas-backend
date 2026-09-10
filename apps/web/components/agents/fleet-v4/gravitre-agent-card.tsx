"use client"

import { cn } from "@/lib/utils"
import { GravitreAgentActivityIndicator } from "./gravitre-agent-activity-indicator"
import { GravitreAgentDepartmentBadge } from "./gravitre-agent-department-badge"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { GravitreAgentStatus } from "./gravitre-agent-status"
import type { FleetAgent } from "./types"

export function GravitreAgentCard({
  agent,
  selected,
  onSelect,
  className,
}: {
  agent: FleetAgent
  selected?: boolean
  onSelect?: (id: string) => void
  className?: string
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(agent.id)}
      className={cn(
        "group w-full rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-3 text-left shadow-[var(--np-shadow)] transition-[border-color,box-shadow]",
        "hover:border-[color:var(--g-brand-border)]",
        selected && "border-[color:var(--g-brand)]/50 ring-2 ring-[color:var(--g-brand)]/40",
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
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-[color:var(--g-text-primary)]">
                {agent.name}
              </p>
              <p className="truncate text-xs text-[color:var(--g-text-muted)]">{agent.role}</p>
            </div>
            <GravitreAgentActivityIndicator runtimeState={agent.runtimeState} />
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
            <GravitreAgentStatus
              runtimeState={agent.runtimeState}
              configState={agent.configState}
              showConfig
            />
            <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
              {agent.tasksToday} tasks today
            </span>
          </div>
          {agent.currentActivity ? (
            <p className="mt-2 truncate text-xs text-[color:var(--g-text-primary)]">
              {agent.currentActivity}
            </p>
          ) : null}
          <div className="mt-2 flex items-center justify-between gap-2">
            <GravitreAgentDepartmentBadge department={agent.department} />
            {agent.successRate != null ? (
              <span className="text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                {agent.successRate}% success · {agent.lastActiveLabel}
              </span>
            ) : null}
          </div>
          <div className="mt-2 hidden gap-2 opacity-0 transition-opacity group-hover:flex group-hover:opacity-100 group-focus-within:flex group-focus-within:opacity-100">
            <span className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-brand)]">
              View
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              Run
            </span>
            <span className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              More
            </span>
          </div>
        </div>
      </div>
    </button>
  )
}
