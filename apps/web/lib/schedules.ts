import cronstrue from "cronstrue"
import { CronExpressionParser } from "cron-parser"
import type { Run, TrainingJob, Workflow, WorkflowSchedule } from "@/types/api"

/**
 * Unified schedules domain model.
 *
 * The Schedules dashboard aggregates three kinds of timed work into one view:
 *  - "workflow": recurring workflow cron schedules
 *  - "task":     individual runs / lite tasks (scheduled or in-flight executions)
 *  - "job":      training jobs
 *
 * There is no single backend endpoint that returns all of these together yet,
 * so the page composes them client-side from existing endpoints and expands
 * cron expressions into concrete occurrences. Live data comes from `GET /api/schedules`
 * via `useSchedules()`; when an org has no data we fall back to a clearly-labelled
 * sample dataset (see `isSample`).
 */

export type ScheduleKind = "workflow" | "task" | "job"

export type ScheduleStatus =
  | "enabled"
  | "disabled"
  | "running"
  | "queued"
  | "completed"
  | "failed"
  | "scheduled"

export interface ScheduledItem {
  id: string
  kind: ScheduleKind
  /** Short human title, e.g. workflow name or task label. */
  title: string
  /** Secondary descriptor, e.g. cron description or status detail. */
  subtitle?: string
  status: ScheduleStatus
  /** Raw cron expression for recurring workflow schedules. */
  cron?: string
  /** ISO timestamp of the next planned run, if known. */
  nextRunAt?: string
  /** ISO timestamp of the most recent run, if known. */
  lastRunAt?: string
  /** ISO timestamp a one-off item started (tasks/jobs). */
  startedAt?: string
  /** ISO timestamp a one-off item completed (tasks/jobs). */
  completedAt?: string
  /** Owning workflow id when relevant. */
  workflowId?: string
  /** 0-100 progress for jobs. */
  progress?: number
  /** Server-projected cron fire timestamps (ISO) within the requested window. */
  occurrences?: string[]
  scheduleType?: "recurring" | "once"
  timezone?: string
  runAt?: string
  endsAt?: string
  name?: string
  /** Free-form details surfaced in the detail panel. */
  meta?: Record<string, string | number | undefined>
  /** Indicates the item came from sample fallback data, not the live backend. */
  isSample?: boolean
}

/** A single point-in-time placement of an item on the timeline/calendar. */
export interface ScheduleOccurrence {
  /** Stable key for React lists. */
  key: string
  item: ScheduledItem
  /** The concrete date/time this occurrence lands on. */
  date: Date
  /** True when this occurrence was projected from a cron expression. */
  projected: boolean
}

// ---------------------------------------------------------------------------
// Color system — theme-stable Gravitre schedule tokens (see globals.css).
// workflow -> purple, task -> blue, job -> green. These keep a consistent hue
// across light/dark (unlike the chart-* tokens, which shift hue per theme).
// ---------------------------------------------------------------------------

export interface KindStyle {
  label: string
  /** CSS color value referencing a brand token. */
  color: string
  /** Tailwind bg utility (token-based) for solid chips. */
  solidBg: string
  /** Tailwind classes for a soft tinted surface. */
  softBg: string
  /** Tailwind text color. */
  text: string
  /** Tailwind border color. */
  border: string
}

export const KIND_STYLES: Record<ScheduleKind, KindStyle> = {
  workflow: {
    label: "Workflow",
    color: "var(--schedule-workflow)",
    solidBg: "bg-[var(--schedule-workflow)]",
    softBg: "bg-[color-mix(in_oklab,var(--schedule-workflow)_15%,transparent)]",
    text: "text-[var(--schedule-workflow)]",
    border: "border-[color-mix(in_oklab,var(--schedule-workflow)_45%,transparent)]",
  },
  task: {
    label: "Task",
    color: "var(--schedule-task)",
    solidBg: "bg-[var(--schedule-task)]",
    softBg: "bg-[color-mix(in_oklab,var(--schedule-task)_15%,transparent)]",
    text: "text-[var(--schedule-task)]",
    border: "border-[color-mix(in_oklab,var(--schedule-task)_45%,transparent)]",
  },
  job: {
    label: "Training job",
    color: "var(--schedule-job)",
    solidBg: "bg-[var(--schedule-job)]",
    softBg: "bg-[color-mix(in_oklab,var(--schedule-job)_16%,transparent)]",
    text: "text-[var(--schedule-job)]",
    border: "border-[color-mix(in_oklab,var(--schedule-job)_45%,transparent)]",
  },
}

export const STATUS_LABELS: Record<ScheduleStatus, string> = {
  enabled: "Enabled",
  disabled: "Disabled",
  running: "Running",
  queued: "Queued",
  completed: "Completed",
  failed: "Failed",
  scheduled: "Scheduled",
}

// ---------------------------------------------------------------------------
// Cron helpers
// ---------------------------------------------------------------------------

/** Human-readable cron description, falling back to the raw expression. */
export function describeCron(expression: string): string {
  try {
    return cronstrue.toString(expression, { use24HourTimeFormat: true })
  } catch {
    return expression
  }
}

/**
 * Expand a cron expression into concrete occurrences inside [from, to].
 * Returns an empty array on parse errors so the UI degrades gracefully.
 */
export function expandCron(
  expression: string,
  from: Date,
  to: Date,
  limit = 200,
): Date[] {
  const out: Date[] = []
  try {
    const interval = CronExpressionParser.parse(expression, {
      currentDate: from,
      endDate: to,
      tz: "UTC",
    })
    while (out.length < limit) {
      const next = interval.next()
      const date = next.toDate()
      if (date > to) break
      out.push(date)
    }
  } catch {
    // Invalid cron — no projected occurrences.
  }
  return out
}

// ---------------------------------------------------------------------------
// Normalizers — convert backend entities into ScheduledItem
// ---------------------------------------------------------------------------

export function fromWorkflowSchedule(
  schedule: WorkflowSchedule,
  workflowName?: string,
): ScheduledItem {
  const cron = schedule.cron_expression || schedule.cronExpression || ""
  const enabled = schedule.isEnabled ?? schedule.enabled
  const scheduleType = schedule.scheduleType || schedule.schedule_type || "recurring"
  const workflowId = schedule.workflowId || schedule.workflow_id
  const name = schedule.name
  const title = name || workflowName || "Workflow schedule"
  return {
    id: `wf-${schedule.id}`,
    kind: "workflow",
    title,
    subtitle: scheduleType === "once" ? "One-time" : describeCron(cron),
    status: enabled ? "enabled" : "disabled",
    cron: cron || undefined,
    nextRunAt: schedule.nextRunAt || schedule.next_run_at,
    lastRunAt: schedule.lastRunAt || schedule.last_run_at,
    workflowId,
    scheduleType,
    timezone: schedule.timezone || "UTC",
    runAt: schedule.runAt || schedule.run_at,
    endsAt: schedule.endsAt || schedule.ends_at,
    name,
    meta: {
      Cron: cron || undefined,
      Type: scheduleType,
      Timezone: schedule.timezone || "UTC",
      Created: schedule.createdAt || schedule.created_at,
    },
  }
}

function mapRunStatus(status: string | undefined): ScheduleStatus {
  switch ((status || "").toLowerCase()) {
    case "running":
    case "in_progress":
      return "running"
    case "queued":
    case "pending":
      return "queued"
    case "completed":
    case "succeeded":
    case "success":
      return "completed"
    case "failed":
    case "error":
      return "failed"
    default:
      return "scheduled"
  }
}

export function fromRun(run: Run): ScheduledItem {
  const started = run.started_at || run.startedAt
  const completed = run.completed_at || run.completedAt
  const name = run.workflow_name || run.workflowName || "Task run"
  return {
    id: `run-${run.id}`,
    kind: "task",
    title: name,
    subtitle: run.run_type ? `${run.run_type} run` : "Run",
    status: mapRunStatus(run.status),
    startedAt: started,
    completedAt: completed,
    lastRunAt: completed || started,
    workflowId: run.workflow_id || run.workflowId,
    meta: {
      Status: run.status,
      "Triggered by": run.triggered_by || run.triggeredBy,
      "Records processed": run.records_processed ?? run.recordsProcessed,
      Duration: run.duration_ms ?? run.durationMs,
    },
  }
}

function mapJobStatus(status: string | undefined): ScheduleStatus {
  switch ((status || "").toLowerCase()) {
    case "training":
      return "running"
    case "queued":
      return "queued"
    case "completed":
      return "completed"
    case "failed":
      return "failed"
    default:
      return "scheduled"
  }
}

export function fromTrainingJob(job: TrainingJob): ScheduledItem {
  return {
    id: `job-${job.id}`,
    kind: "job",
    title: job.dataset_name || "Training job",
    subtitle: job.model_base ? `Fine-tune · ${job.model_base}` : "Training job",
    status: mapJobStatus(job.status),
    startedAt: job.started_at,
    completedAt: job.completed_at,
    lastRunAt: job.completed_at || job.started_at || job.created_at,
    progress: job.progress,
    meta: {
      "Base model": job.model_base,
      Progress: typeof job.progress === "number" ? `${job.progress}%` : undefined,
      Accuracy: job.metrics?.accuracy,
      Loss: job.metrics?.loss,
    },
  }
}

// ---------------------------------------------------------------------------
// Occurrence projection
// ---------------------------------------------------------------------------

/**
 * Build the list of occurrences to render for the given range.
 * - Workflow schedules with a cron are expanded across the range.
 * - Workflow schedules without a parseable cron fall back to their nextRunAt.
 * - Tasks/jobs are placed on their last/next known timestamp.
 */
export function buildOccurrences(
  items: ScheduledItem[],
  from: Date,
  to: Date,
): ScheduleOccurrence[] {
  const occurrences: ScheduleOccurrence[] = []

  for (const item of items) {
    if (item.kind === "workflow" && (item.cron || item.occurrences?.length)) {
      // Prefer server-projected occurrences when present; otherwise expand the
      // cron client-side across the requested window.
      const serverDates = (item.occurrences ?? [])
        .map((iso) => new Date(iso))
        .filter((d) => !Number.isNaN(d.getTime()) && d >= from && d <= to)
      const dates =
        serverDates.length > 0 ? serverDates : item.cron ? expandCron(item.cron, from, to) : []
      for (const date of dates) {
        occurrences.push({
          key: `${item.id}-${date.getTime()}`,
          item,
          date,
          projected: true,
        })
      }
      // If cron produced nothing but we know the next run, still place it.
      if (dates.length === 0 && item.nextRunAt) {
        const date = new Date(item.nextRunAt)
        if (date >= from && date <= to) {
          occurrences.push({ key: `${item.id}-next`, item, date, projected: true })
        }
      }
      continue
    }

    const stamp = item.nextRunAt || item.completedAt || item.startedAt || item.lastRunAt
    if (!stamp) continue
    const date = new Date(stamp)
    if (Number.isNaN(date.getTime())) continue
    if (date < from || date > to) continue
    occurrences.push({ key: item.id, item, date, projected: false })
  }

  return occurrences.sort((a, b) => a.date.getTime() - b.date.getTime())
}

// ---------------------------------------------------------------------------
// Sample fallback data (clearly labelled via isSample)
// ---------------------------------------------------------------------------

/** Generate sample items anchored around `anchor` so the UI is never empty. */
export function sampleScheduledItems(anchor = new Date()): ScheduledItem[] {
  const day = (offset: number, hour = 9, minute = 0) => {
    const d = new Date(anchor)
    d.setDate(d.getDate() + offset)
    d.setHours(hour, minute, 0, 0)
    return d.toISOString()
  }

  return [
    {
      id: "sample-wf-1",
      kind: "workflow",
      title: "Daily data sync",
      subtitle: describeCron("0 6 * * *"),
      status: "enabled",
      cron: "0 6 * * *",
      nextRunAt: day(0, 6),
      lastRunAt: day(-1, 6),
      isSample: true,
      meta: { Cron: "0 6 * * *", Owner: "Operations" },
    },
    {
      id: "sample-wf-2",
      kind: "workflow",
      title: "Weekday standup digest",
      subtitle: describeCron("0 9 * * 1-5"),
      status: "enabled",
      cron: "0 9 * * 1-5",
      nextRunAt: day(1, 9),
      lastRunAt: day(-1, 9),
      isSample: true,
      meta: { Cron: "0 9 * * 1-5", Owner: "Revenue" },
    },
    {
      id: "sample-wf-3",
      kind: "workflow",
      title: "Monthly invoice rollup",
      subtitle: describeCron("0 0 1 * *"),
      status: "disabled",
      cron: "0 0 1 * *",
      nextRunAt: day(6, 0),
      isSample: true,
      meta: { Cron: "0 0 1 * *", Owner: "Finance" },
    },
    {
      id: "sample-task-1",
      kind: "task",
      title: "Lead enrichment run",
      subtitle: "Scheduled run",
      status: "running",
      startedAt: day(0, 11),
      lastRunAt: day(0, 11),
      isSample: true,
      meta: { Status: "running", "Triggered by": "Schedule" },
    },
    {
      id: "sample-task-2",
      kind: "task",
      title: "Inbox triage",
      subtitle: "Completed run",
      status: "completed",
      completedAt: day(-1, 14),
      lastRunAt: day(-1, 14),
      isSample: true,
      meta: { Status: "completed", "Records processed": 128 },
    },
    {
      id: "sample-task-3",
      kind: "task",
      title: "Report export",
      subtitle: "Failed run",
      status: "failed",
      completedAt: day(2, 16),
      lastRunAt: day(2, 16),
      isSample: true,
      meta: { Status: "failed", Error: "Timeout" },
    },
    {
      id: "sample-job-1",
      kind: "job",
      title: "Support classifier",
      subtitle: "Fine-tune · gpt-4o-mini",
      status: "running",
      startedAt: day(0, 13),
      lastRunAt: day(0, 13),
      progress: 62,
      isSample: true,
      meta: { "Base model": "gpt-4o-mini", Progress: "62%" },
    },
    {
      id: "sample-job-2",
      kind: "job",
      title: "Intent ranker",
      subtitle: "Fine-tune · gpt-4o-mini",
      status: "completed",
      completedAt: day(3, 10),
      lastRunAt: day(3, 10),
      progress: 100,
      isSample: true,
      meta: { "Base model": "gpt-4o-mini", Accuracy: 0.94 },
    },
  ]
}

/** Legacy client-side aggregation when `GET /api/schedules` is unavailable. */
export async function aggregateSchedulesClientSide(deps: {
  listWorkflows: () => Promise<{ workflows: Workflow[] }>
  listSchedules: (workflowId: string) => Promise<{ schedules: WorkflowSchedule[] }>
  listRuns: (params?: { workflow_id?: string; limit?: number }) => Promise<{ runs: Run[] }>
  listJobs: () => Promise<{ jobs: TrainingJob[] }>
  workflowId?: string
}): Promise<ScheduledItem[]> {
  const items: ScheduledItem[] = []

  try {
    let workflows: { id: string; name: string }[] = []
    if (deps.workflowId) {
      workflows = [{ id: deps.workflowId, name: "Workflow" }]
    } else {
      const res = await deps.listWorkflows()
      workflows = (res.workflows ?? []).map((workflow) => ({
        id: workflow.id,
        name: workflow.name,
      }))
    }

    const scheduleResults = await Promise.all(
      workflows.map(async (workflow) => {
        try {
          const res = await deps.listSchedules(workflow.id)
          return (res.schedules ?? []).map((schedule) => fromWorkflowSchedule(schedule, workflow.name))
        } catch {
          return []
        }
      }),
    )
    for (const group of scheduleResults) items.push(...group)
  } catch {
    // ignore — caller may fall back to sample data
  }

  try {
    const res = await deps.listRuns(
      deps.workflowId ? { workflow_id: deps.workflowId, limit: 100 } : { limit: 100 },
    )
    for (const run of res.runs ?? []) items.push(fromRun(run))
  } catch {
    // ignore
  }

  if (!deps.workflowId) {
    try {
      const res = await deps.listJobs()
      for (const job of res.jobs ?? []) items.push(fromTrainingJob(job))
    } catch {
      // ignore
    }
  }

  return items.sort((a, b) => {
    const aTime = a.nextRunAt || a.startedAt || a.lastRunAt || ""
    const bTime = b.nextRunAt || b.startedAt || b.lastRunAt || ""
    return bTime.localeCompare(aTime)
  })
}
