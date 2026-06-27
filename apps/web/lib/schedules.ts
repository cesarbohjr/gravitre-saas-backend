import type { Run, RunStatus, ScheduledItem, ScheduledItemStatus, TrainingJob, Workflow, WorkflowSchedule } from "@/types/api"

function mapRunStatus(status: RunStatus | string): ScheduledItemStatus {
  switch (status) {
    case "running":
    case "paused":
      return "running"
    case "completed":
      return "completed"
    case "failed":
    case "rejected":
    case "cancelled":
      return "failed"
    case "pending":
    case "pending_approval":
    case "awaiting_approval":
    case "approved":
      return "queued"
    default:
      return "scheduled"
  }
}

function mapJobStatus(status: TrainingJob["status"]): ScheduledItemStatus {
  switch (status) {
    case "training":
      return "running"
    case "completed":
      return "completed"
    case "failed":
      return "failed"
    case "queued":
      return "queued"
    default:
      return "scheduled"
  }
}

function scheduleEnabled(schedule: WorkflowSchedule & Record<string, unknown>): boolean {
  if (typeof schedule.enabled === "boolean") return schedule.enabled
  if (typeof schedule.isEnabled === "boolean") return schedule.isEnabled
  return true
}

function scheduleCron(schedule: WorkflowSchedule & Record<string, unknown>): string {
  return String(schedule.cron_expression || schedule.cronExpression || "").trim()
}

export function workflowScheduleToScheduledItem(
  schedule: WorkflowSchedule & Record<string, unknown>,
  workflowName?: string,
): ScheduledItem {
  const cron = scheduleCron(schedule)
  const enabled = scheduleEnabled(schedule)
  const workflowId = String(schedule.workflow_id || schedule.workflowId || "")
  return {
    kind: "workflow",
    id: String(schedule.id),
    title: workflowName || "Workflow schedule",
    subtitle: cron || undefined,
    status: enabled ? "enabled" : "disabled",
    cron: cron || undefined,
    nextRunAt: (schedule.next_run_at || schedule.nextRunAt) as string | undefined,
    lastRunAt: (schedule.last_run_at || schedule.lastRunAt) as string | undefined,
    workflowId: workflowId || undefined,
  }
}

export function runToScheduledItem(run: Run): ScheduledItem {
  const workflowId = String(run.workflow_id || run.workflowId || "")
  const title = run.workflow_name || run.workflowName || "Workflow run"
  return {
    kind: "task",
    id: String(run.id),
    title,
    subtitle: run.status.replace(/_/g, " "),
    status: mapRunStatus(run.status),
    workflowId: workflowId || undefined,
    startedAt: (run.started_at || run.startedAt || run.created_at) as string | undefined,
    completedAt: (run.completed_at || run.completedAt) as string | undefined,
  }
}

export function trainingJobToScheduledItem(job: TrainingJob): ScheduledItem {
  return {
    kind: "job",
    id: String(job.id),
    title: `Training job (${job.model_base})`,
    subtitle: job.dataset_name || job.status,
    status: mapJobStatus(job.status),
    progress: job.progress,
    startedAt: job.started_at,
    completedAt: job.completed_at,
  }
}

export function mergeScheduledItems(items: ScheduledItem[]): ScheduledItem[] {
  return [...items].sort((a, b) => {
    const aTime = a.nextRunAt || a.startedAt || a.lastRunAt || ""
    const bTime = b.nextRunAt || b.startedAt || b.lastRunAt || ""
    return bTime.localeCompare(aTime)
  })
}

export async function aggregateSchedulesClientSide(deps: {
  listWorkflows: () => Promise<{ workflows: Workflow[] }>
  listSchedules: (workflowId: string) => Promise<{ schedules: WorkflowSchedule[] }>
  listRuns: () => Promise<{ runs: Run[] }>
  listJobs: () => Promise<{ jobs: TrainingJob[] }>
  workflowId?: string
}): Promise<ScheduledItem[]> {
  const [{ workflows }, { runs }, { jobs }] = await Promise.all([
    deps.listWorkflows(),
    deps.listRuns(),
    deps.listJobs(),
  ])

  const workflowList = deps.workflowId
    ? workflows.filter((workflow) => workflow.id === deps.workflowId)
    : workflows
  const workflowNames = new Map(workflowList.map((workflow) => [workflow.id, workflow.name]))

  const scheduleGroups = await Promise.all(
    workflowList.map(async (workflow) => {
      const { schedules } = await deps.listSchedules(workflow.id)
      return schedules.map((schedule) =>
        workflowScheduleToScheduledItem(
          schedule as WorkflowSchedule & Record<string, unknown>,
          workflowNames.get(workflow.id),
        ),
      )
    }),
  )

  const taskItems = runs
    .filter((run) => !deps.workflowId || run.workflow_id === deps.workflowId || run.workflowId === deps.workflowId)
    .map(runToScheduledItem)

  const jobItems = deps.workflowId ? [] : jobs.map(trainingJobToScheduledItem)

  return mergeScheduledItems([...scheduleGroups.flat(), ...taskItems, ...jobItems])
}
