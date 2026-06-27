"use client"

import { cn } from "@/lib/utils"
import { KIND_STYLES, STATUS_LABELS, type ScheduleKind, type ScheduleStatus } from "@/lib/schedules"

/** A small color dot representing an item kind, using Gravitre brand tokens. */
export function KindDot({ kind, className }: { kind: ScheduleKind; className?: string }) {
  return (
    <span
      className={cn("inline-block h-2.5 w-2.5 shrink-0 rounded-full", className)}
      style={{ backgroundColor: KIND_STYLES[kind].color }}
      aria-hidden
    />
  )
}

/** A soft-tinted chip labelling an item kind. */
export function KindBadge({ kind, className }: { kind: ScheduleKind; className?: string }) {
  const style = KIND_STYLES[kind]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        style.softBg,
        style.text,
        style.border,
        className,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: style.color }} />
      {style.label}
    </span>
  )
}

const STATUS_VARIANT: Record<ScheduleStatus, "success" | "warning" | "error" | "info" | "muted" | "default"> = {
  enabled: "success",
  completed: "success",
  running: "info",
  queued: "warning",
  scheduled: "default",
  disabled: "muted",
  failed: "error",
}

export function statusVariant(status: ScheduleStatus) {
  return STATUS_VARIANT[status]
}

export function statusLabel(status: ScheduleStatus) {
  return STATUS_LABELS[status]
}

/** Legend explaining the color coding. */
export function ScheduleLegend({ className }: { className?: string }) {
  const kinds: ScheduleKind[] = ["workflow", "task", "job"]
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-2", className)}>
      {kinds.map((kind) => (
        <span key={kind} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <KindDot kind={kind} />
          {KIND_STYLES[kind].label}
        </span>
      ))}
    </div>
  )
}

// --- date helpers (UTC-agnostic, local display) ---

export function formatDateTime(value?: string | Date): string {
  if (!value) return "—"
  const d = typeof value === "string" ? new Date(value) : value
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function formatTime(value?: string | Date): string {
  if (!value) return ""
  const d = typeof value === "string" ? new Date(value) : value
  if (Number.isNaN(d.getTime())) return ""
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

export function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0, 23, 59, 59, 999)
}

/** First day of the calendar grid (Monday-based) containing the month of `d`. */
export function startOfCalendarGrid(d: Date): Date {
  const first = startOfMonth(d)
  const weekday = (first.getDay() + 6) % 7 // 0 = Monday
  const start = new Date(first)
  start.setDate(first.getDate() - weekday)
  start.setHours(0, 0, 0, 0)
  return start
}

export function addDays(d: Date, days: number): Date {
  const next = new Date(d)
  next.setDate(next.getDate() + days)
  return next
}
