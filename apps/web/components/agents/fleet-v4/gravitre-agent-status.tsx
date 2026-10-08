"use client"

import { cn } from "@/lib/utils"
import type { AgentConfigState, AgentRuntimeState } from "./types"

// Runtime states map onto the semantic status tokens (success / info /
// warning / destructive / muted) so pills match status colours elsewhere in the
// app; "live" states share the info hue and are distinguished by pulse + label.
const RUNTIME_META: Record<
  AgentRuntimeState,
  { label: string; dotClass: string; pillClass: string; live?: boolean }
> = {
  available: {
    label: "Available",
    dotClass: "bg-success",
    pillClass: "text-success bg-success/10",
  },
  idle: {
    label: "Idle",
    dotClass: "bg-muted-foreground/60",
    pillClass: "text-muted-foreground bg-muted",
  },
  thinking: {
    label: "Thinking",
    dotClass: "bg-info",
    pillClass: "text-info bg-info/10",
    live: true,
  },
  retrieving: {
    label: "Retrieving",
    dotClass: "bg-info",
    pillClass: "text-info bg-info/10",
    live: true,
  },
  planning: {
    label: "Planning",
    dotClass: "bg-info",
    pillClass: "text-info bg-info/10",
    live: true,
  },
  executing: {
    label: "Executing",
    dotClass: "bg-info",
    pillClass: "text-info bg-info/10",
    live: true,
  },
  waiting_approval: {
    label: "Waiting approval",
    dotClass: "bg-warning",
    pillClass: "text-warning bg-warning/10",
  },
  delegating: {
    label: "Delegating",
    dotClass: "bg-primary",
    pillClass: "text-primary bg-primary/10",
    live: true,
  },
  completed: {
    label: "Completed",
    dotClass: "bg-success/70",
    pillClass: "text-success bg-success/5",
  },
  failed: {
    label: "Failed",
    dotClass: "bg-destructive",
    pillClass: "text-destructive bg-destructive/10",
  },
  blocked: {
    label: "Blocked",
    dotClass: "bg-warning",
    pillClass: "text-warning bg-warning/15",
  },
  offline: {
    label: "Offline",
    dotClass: "bg-muted-foreground/40",
    pillClass: "text-muted-foreground bg-muted/70",
  },
}

const CONFIG_LABEL: Record<AgentConfigState, string> = {
  enabled: "Enabled",
  paused: "Paused",
  disabled: "Disabled",
}

export function GravitreAgentStatusDot({
  state,
  className,
}: {
  state: AgentRuntimeState
  className?: string
}) {
  const meta = RUNTIME_META[state]
  return (
    <span
      className={cn(
        "block h-2 w-2 rounded-full ring-2 ring-[color:var(--g-surface-1)]",
        meta.dotClass,
        meta.live && "animate-pulse",
        className,
      )}
      title={meta.label}
    />
  )
}

export function GravitreAgentStatus({
  runtimeState,
  configState,
  showConfig = false,
  className,
}: {
  runtimeState: AgentRuntimeState
  configState?: AgentConfigState
  showConfig?: boolean
  className?: string
}) {
  const meta = RUNTIME_META[runtimeState]
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1.5", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
          meta.pillClass,
        )}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", meta.dotClass, meta.live && "animate-pulse")} />
        {meta.label}
      </span>
      {showConfig && configState && configState !== "enabled" ? (
        <span className="text-[11px] text-[color:var(--g-text-muted)]">{CONFIG_LABEL[configState]}</span>
      ) : null}
    </span>
  )
}

export function isRuntimeWorking(state: AgentRuntimeState): boolean {
  return Boolean(RUNTIME_META[state].live)
}
