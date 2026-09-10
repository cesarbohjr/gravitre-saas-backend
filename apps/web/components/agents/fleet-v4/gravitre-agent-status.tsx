"use client"

import { cn } from "@/lib/utils"
import type { AgentConfigState, AgentRuntimeState } from "./types"

const RUNTIME_META: Record<
  AgentRuntimeState,
  { label: string; dotClass: string; pillClass: string; live?: boolean }
> = {
  available: {
    label: "Available",
    dotClass: "bg-emerald-500",
    pillClass: "text-emerald-800 dark:text-emerald-200 bg-emerald-50/80 dark:bg-emerald-950/30",
  },
  idle: {
    label: "Idle",
    dotClass: "bg-zinc-400",
    pillClass: "text-zinc-600 dark:text-zinc-300 bg-zinc-100/80 dark:bg-zinc-900/40",
  },
  thinking: {
    label: "Thinking",
    dotClass: "bg-sky-500",
    pillClass: "text-sky-800 dark:text-sky-200 bg-sky-50/80 dark:bg-sky-950/30",
    live: true,
  },
  retrieving: {
    label: "Retrieving",
    dotClass: "bg-cyan-500",
    pillClass: "text-cyan-800 dark:text-cyan-200 bg-cyan-50/80 dark:bg-cyan-950/30",
    live: true,
  },
  planning: {
    label: "Planning",
    dotClass: "bg-indigo-500",
    pillClass: "text-indigo-800 dark:text-indigo-200 bg-indigo-50/80 dark:bg-indigo-950/30",
    live: true,
  },
  executing: {
    label: "Executing",
    dotClass: "bg-blue-500",
    pillClass: "text-blue-800 dark:text-blue-200 bg-blue-50/80 dark:bg-blue-950/30",
    live: true,
  },
  waiting_approval: {
    label: "Waiting approval",
    dotClass: "bg-amber-500",
    pillClass: "text-amber-900 dark:text-amber-100 bg-amber-50/80 dark:bg-amber-950/30",
  },
  delegating: {
    label: "Delegating",
    dotClass: "bg-violet-500",
    pillClass: "text-violet-800 dark:text-violet-200 bg-violet-50/80 dark:bg-violet-950/30",
    live: true,
  },
  completed: {
    label: "Completed",
    dotClass: "bg-emerald-400",
    pillClass: "text-emerald-800 dark:text-emerald-200 bg-emerald-50/60 dark:bg-emerald-950/20",
  },
  failed: {
    label: "Failed",
    dotClass: "bg-rose-500",
    pillClass: "text-rose-800 dark:text-rose-200 bg-rose-50/80 dark:bg-rose-950/30",
  },
  blocked: {
    label: "Blocked",
    dotClass: "bg-orange-500",
    pillClass: "text-orange-900 dark:text-orange-100 bg-orange-50/80 dark:bg-orange-950/30",
  },
  offline: {
    label: "Offline",
    dotClass: "bg-zinc-400",
    pillClass: "text-zinc-600 dark:text-zinc-300 bg-zinc-100/80 dark:bg-zinc-900/40",
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
