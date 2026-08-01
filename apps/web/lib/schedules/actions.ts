import type { ScheduledItem } from "@/lib/schedules"
import { workflowsApi, runsApi, trainingApi } from "@/lib/api"

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

export function parseScheduledItemIds(item: ScheduledItem): {
  scheduleId?: string
  runId?: string
  jobId?: string
} {
  if (item.id.startsWith("wf-")) {
    return { scheduleId: item.id.slice(3) }
  }
  if (item.id.startsWith("run-")) {
    return { runId: item.id.slice(4) }
  }
  if (item.id.startsWith("job-")) {
    return { jobId: item.id.slice(4) }
  }
  if (UUID_PATTERN.test(item.id)) {
    if (item.kind === "workflow") return { scheduleId: item.id }
    if (item.kind === "task") return { runId: item.id }
    return { jobId: item.id }
  }
  return {}
}

export function cronForDateTime(date: Date): string {
  const minute = date.getMinutes()
  const hour = date.getHours()
  const day = date.getDate()
  const month = date.getMonth() + 1
  return `${minute} ${hour} ${day} ${month} *`
}

export function scheduleDeleteLabel(item: ScheduledItem): string {
  if (item.kind === "workflow") return "Delete workflow schedule"
  if (item.kind === "task") return "Cancel scheduled task"
  return "Remove training job"
}

export function scheduleDeleteDescription(item: ScheduledItem): string {
  if (item.kind === "workflow") {
    return `This removes the recurring schedule for "${item.title}". The workflow itself will not be deleted.`
  }
  if (item.kind === "task") {
    return `This cancels "${item.title}". If the task is already running, it will be stopped.`
  }
  return `This removes "${item.title}" from your schedule view.`
}

export function scheduleMoveDescription(item: ScheduledItem, targetDate: Date): string {
  const when = targetDate.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
  if (item.kind === "workflow") {
    if (item.scheduleType === "once") {
      return `Move "${item.title}" to ${when}? This updates the one-time run.`
    }
    return `Move "${item.title}" to ${when}? This converts the schedule to a one-time run at that time (edit the schedule to keep a recurrence).`
  }
  if (item.kind === "task") {
    return `Move "${item.title}" to ${when}? Only pending or queued tasks can be rescheduled.`
  }
  return `Move "${item.title}" to ${when}?`
}

export function scheduleEditHref(
  item: ScheduledItem,
  ids: ReturnType<typeof parseScheduledItemIds>,
): string | null {
  if (item.isSample) return null
  if (item.kind === "workflow" && item.workflowId) {
    return `/workflows/${item.workflowId}/schedules`
  }
  if (item.kind === "task" && ids.runId) {
    return `/runs/${ids.runId}`
  }
  if (item.kind === "job") {
    return ids.jobId ? `/training?job=${ids.jobId}` : "/training"
  }
  return null
}

export function scheduleEditLabel(item: ScheduledItem): string {
  if (item.kind === "workflow") return "Edit workflow schedule"
  if (item.kind === "task") return "Open task run"
  return "Open training job"
}

export function canMoveScheduleItem(item: ScheduledItem): boolean {
  if (item.isSample) return false
  const ids = parseScheduledItemIds(item)
  if (item.kind === "workflow") return Boolean(item.workflowId && ids.scheduleId)
  if (item.kind === "task") {
    return Boolean(ids.runId && ["scheduled", "queued", "pending"].includes(item.status))
  }
  return false
}

export function canDeleteScheduleItem(item: ScheduledItem): boolean {
  if (item.isSample) return false
  const ids = parseScheduledItemIds(item)
  if (item.kind === "workflow") return Boolean(item.workflowId && ids.scheduleId)
  if (item.kind === "task") return Boolean(ids.runId)
  if (item.kind === "job") {
    return Boolean(ids.jobId && ["scheduled", "queued", "running"].includes(item.status))
  }
  return false
}

export function toDateTimeLocalValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function parseDateTimeLocalValue(value: string): Date | null {
  if (!value.trim()) return null
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export async function moveScheduledItem(
  item: ScheduledItem,
  targetDate: Date,
): Promise<void> {
  const ids = parseScheduledItemIds(item)
  if (item.isSample) {
    throw new Error("Sample schedules cannot be moved")
  }
  if (item.kind === "workflow" && item.workflowId && ids.scheduleId) {
    // Calendar drag/reschedule always sets an absolute one-time fire — avoids yearly cron traps.
    await workflowsApi.updateSchedule(item.workflowId, ids.scheduleId, {
      scheduleType: "once",
      runAt: targetDate.toISOString(),
      timezone: item.timezone || "UTC",
      enabled: item.status !== "disabled",
      name: item.name,
    })
    return
  }
  if (item.kind === "task" && ids.runId) {
    if (!["scheduled", "queued", "pending"].includes(item.status)) {
      throw new Error("Only pending tasks can be moved")
    }
    await runsApi.cancel(ids.runId)
    throw new Error("Create a new schedule from the workflow to run this task at the new time.")
  }
  throw new Error("This schedule type cannot be moved from the calendar")
}

export async function deleteScheduledItem(item: ScheduledItem): Promise<void> {
  const ids = parseScheduledItemIds(item)
  if (item.kind === "workflow" && item.workflowId && ids.scheduleId) {
    await workflowsApi.deleteSchedule(item.workflowId, ids.scheduleId)
    return
  }
  if (item.kind === "task" && ids.runId) {
    await runsApi.cancel(ids.runId)
    return
  }
  if (item.kind === "job" && ids.jobId) {
    await trainingApi.cancelJob(ids.jobId)
    return
  }
  throw new Error("This item cannot be deleted from the calendar")
}
