"use client"

import type { ReactNode } from "react"
import { AlertTriangle, Check, Circle, Hand, Loader2, OctagonX } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * One unit of AI work, bound to a state the runtime actually reports.
 * No progress percentages: the state glyph and label are the whole signal.
 */
export type TaskRowState = "done" | "running" | "waiting" | "blocked" | "failed" | "pending"

const STATE: Record<TaskRowState, { label: string; icon: typeof Check; tone: string; spin?: boolean }> = {
  done: { label: "Completed", icon: Check, tone: "text-[color:var(--g-brand)]" },
  running: { label: "Running", icon: Loader2, tone: "text-foreground", spin: true },
  waiting: { label: "Waiting for approval", icon: Hand, tone: "text-warning" },
  blocked: { label: "Blocked", icon: AlertTriangle, tone: "text-warning" },
  failed: { label: "Failed", icon: OctagonX, tone: "text-destructive" },
  pending: { label: "Not started", icon: Circle, tone: "text-muted-foreground" },
}

export function taskRowStateLabel(state: TaskRowState): string {
  return STATE[state].label
}

export function GravitreTaskRow({
  state,
  title,
  detail,
  meta,
  stateLabel,
  action,
  leading,
  className,
}: {
  state: TaskRowState
  title: ReactNode
  detail?: ReactNode
  meta?: ReactNode
  /** Overrides the default state label (e.g. "Reconnect required"). */
  stateLabel?: string
  action?: ReactNode
  /** Replaces the state glyph, e.g. a provider logo; the state label still shows. */
  leading?: ReactNode
  className?: string
}) {
  const s = STATE[state]
  const Icon = s.icon
  return (
    <li
      data-task-row={state}
      className={cn(
        "flex items-start gap-3 border-b border-[color:var(--g-border-subtle)] py-2.5 last:border-b-0",
        className,
      )}
    >
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden>
        {leading ?? <Icon className={cn("h-4 w-4", s.tone, s.spin && "animate-spin motion-reduce:animate-none")} strokeWidth={2} />}
      </span>
      <span className="min-w-0 flex-1">
        <span
          className={cn(
            "block text-[13px] leading-snug",
            state === "pending" ? "text-muted-foreground" : "font-medium text-foreground",
          )}
        >
          {title}
        </span>
        {detail ? <span className="mt-0.5 block text-[12px] leading-snug text-muted-foreground">{detail}</span> : null}
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <span className={cn("inline-flex items-center gap-1.5 text-[11.5px] font-medium", state === "done" ? "text-muted-foreground" : s.tone)}>
          {leading ? <Icon className={cn("h-3.5 w-3.5", s.spin && "animate-spin motion-reduce:animate-none")} aria-hidden /> : null}
          {stateLabel ?? s.label}
        </span>
        {meta ? <span className="text-[11px] tabular-nums text-muted-foreground">{meta}</span> : null}
        {action}
      </span>
    </li>
  )
}

export function GravitreTaskList({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <ul aria-label={label} className={cn("min-w-0", className)}>
      {children}
    </ul>
  )
}
