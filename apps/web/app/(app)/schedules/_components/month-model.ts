/**
 * Schedules month calendar model. Turns scheduled items (workflow schedules,
 * task runs, training jobs) into dated entries in four run states the page
 * filters on, and derives the month's counts, day agenda and failure hotspots.
 *
 * Projected schedule fires are only shown in the future: a fire time that has
 * passed shows up as the run it produced, never twice.
 */
import { buildOccurrences, type ScheduleOccurrence, type ScheduledItem } from "@/lib/schedules"

export type RunState = "running" | "scheduled" | "failed" | "completed"

export const RUN_STATES: RunState[] = ["running", "scheduled", "failed", "completed"]

export const RUN_STATE_LABEL: Record<RunState, string> = {
  running: "Running",
  scheduled: "Scheduled",
  failed: "Failed",
  completed: "Completed",
}

export type CalendarEntry = {
  key: string
  occurrence: ScheduleOccurrence
  state: RunState
  date: Date
  name: string
  workflowId: string | null
}

export function runStateOf(occurrence: ScheduleOccurrence, now: Date): RunState | null {
  const { item } = occurrence
  if (item.kind === "workflow") {
    if (item.status === "disabled") return null
    return occurrence.date.getTime() >= now.getTime() ? "scheduled" : null
  }
  switch (item.status) {
    case "running":
      return "running"
    case "queued":
    case "scheduled":
    case "enabled":
      return "scheduled"
    case "failed":
      return "failed"
    case "completed":
      return "completed"
    default:
      return null
  }
}

export function entryName(item: ScheduledItem): string {
  if (item.workflowName) return item.workflowName
  return item.title.replace(/^Run · /, "")
}

export function buildEntries(items: ScheduledItem[], from: Date, to: Date, now: Date): CalendarEntry[] {
  const out: CalendarEntry[] = []
  for (const occurrence of buildOccurrences(items, from, to)) {
    const state = runStateOf(occurrence, now)
    if (!state) continue
    // Runs sit on the calendar at the time they started, not when they finished.
    const started = occurrence.item.kind !== "workflow" && occurrence.item.startedAt ? new Date(occurrence.item.startedAt) : null
    const date = started && !Number.isNaN(started.getTime()) ? started : occurrence.date
    out.push({
      key: occurrence.key,
      occurrence,
      state,
      date,
      name: entryName(occurrence.item),
      workflowId: occurrence.item.workflowId ?? null,
    })
  }
  return out.sort((a, b) => a.date.getTime() - b.date.getTime())
}

export function dayKey(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

export function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1)
}

/** Six Monday-first weeks covering the month. */
export function monthGrid(month: Date): Date[] {
  const first = startOfMonth(month)
  const offset = (first.getDay() + 6) % 7 // Monday = 0
  const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset)
  return Array.from({ length: 42 }, (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i))
}

/** Drop the last week when it is entirely in the next month. */
export function trimGrid(days: Date[], month: Date): Date[] {
  const lastWeek = days.slice(35)
  return lastWeek.every((d) => d.getMonth() !== month.getMonth()) ? days.slice(0, 35) : days
}

export function groupByDay(entries: CalendarEntry[]): Map<string, CalendarEntry[]> {
  const map = new Map<string, CalendarEntry[]>()
  for (const entry of entries) {
    const key = dayKey(entry.date)
    const bucket = map.get(key)
    if (bucket) bucket.push(entry)
    else map.set(key, [entry])
  }
  return map
}

export function countStates(entries: CalendarEntry[]): Record<RunState, number> {
  const out: Record<RunState, number> = { running: 0, scheduled: 0, failed: 0, completed: 0 }
  for (const entry of entries) out[entry.state] += 1
  return out
}

/** Completed over finished runs, or null when nothing finished. */
export function successPercent(entries: CalendarEntry[]): number | null {
  const counts = countStates(entries)
  const finished = counts.completed + counts.failed
  return finished ? Math.round((counts.completed / finished) * 100) : null
}

export function hotspots(entries: CalendarEntry[], limit = 5): Array<{ name: string; count: number }> {
  const counts = new Map<string, number>()
  for (const entry of entries) {
    if (entry.state !== "failed") continue
    counts.set(entry.name, (counts.get(entry.name) ?? 0) + 1)
  }
  return Array.from(counts, ([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
    .slice(0, limit)
}

const CREDENTIAL_PATTERN = /token|expired|unauthori[sz]ed|reconnect|re-?auth|sign[\s-]?in|credential|\b401\b|\b403\b|oauth/i

/** Failed runs whose recorded error mentions a sign-in or credential problem (literal match). */
export function credentialFailures(entries: CalendarEntry[]): number {
  return entries.filter((entry) => entry.state === "failed" && CREDENTIAL_PATTERN.test(entry.occurrence.item.error ?? "")).length
}

/**
 * The latest failed run of each workflow. Retrying starts a fresh run, so a
 * workflow that failed five times is retried once, not five times.
 */
export function latestFailedPerWorkflow(entries: CalendarEntry[]): CalendarEntry[] {
  const latest = new Map<string, CalendarEntry>()
  for (const entry of entries) {
    if (entry.state !== "failed" || entry.occurrence.item.kind !== "task") continue
    const key = entry.workflowId ?? entry.occurrence.item.id
    const current = latest.get(key)
    if (!current || current.date.getTime() < entry.date.getTime()) latest.set(key, entry)
  }
  return Array.from(latest.values())
}

export function formatDuration(ms: number | undefined): string | null {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms < 0) return null
  const secs = Math.round(ms / 1000)
  if (secs < 60) return `${secs}s`
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ${secs % 60}s`
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

export function timeLabel(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`
}

export function agendaLine(entry: CalendarEntry): string {
  const duration = formatDuration(entry.occurrence.item.durationMs)
  const label = RUN_STATE_LABEL[entry.state]
  if (entry.state === "scheduled") {
    const subtitle = entry.occurrence.item.kind === "workflow" ? "Schedule" : "Queued"
    return `${label} · ${subtitle}`
  }
  return duration ? `${label} · ${duration}` : label
}
