import type { ScheduledItem } from "@/lib/schedules"

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
    return `Move "${item.title}" to ${when}? This updates the recurring schedule time.`
  }
  if (item.kind === "task") {
    return `Move "${item.title}" to ${when}? Only pending or queued tasks can be rescheduled.`
  }
  return `Move "${item.title}" to ${when}?`
}
