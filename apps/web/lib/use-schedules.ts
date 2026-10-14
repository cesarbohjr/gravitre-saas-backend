"use client"

import useSWR from "swr"

import {
  aggregateSchedulesClientSide,
  type ScheduledItem,
} from "@/lib/schedules"
import { runsApi, schedulesApi, trainingApi, workflowsApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { ScheduledItem as ApiScheduledItem, SchedulesListParams } from "@/types/api"

export type UseSchedulesOptions = SchedulesListParams & {
  enabled?: boolean
  preferUnifiedEndpoint?: boolean
}

export interface UseSchedulesResult {
  items: ScheduledItem[]
  isLoading: boolean
  error: unknown
  /** Always false — sample fallback removed; empty state shown instead. */
  isSample: boolean
  /**
   * How much of the window's run history is present:
   * "complete"  the unified endpoint read every run in the window;
   * "truncated" it hit its read ceiling, so the oldest runs are missing;
   * "unknown"   the legacy fan-out served the data, which only reads the latest 100 runs.
   */
  coverage: ScheduleCoverage
  refresh: () => void
}

function mapApiItem(item: ApiScheduledItem): ScheduledItem {
  return {
    kind: item.kind,
    id: item.id,
    title: item.title,
    subtitle: item.subtitle,
    status: item.status,
    cron: item.cron,
    nextRunAt: item.nextRunAt,
    lastRunAt: item.lastRunAt,
    startedAt: item.startedAt,
    completedAt: item.completedAt,
    workflowId: item.workflowId,
    progress: item.progress,
    occurrences: item.occurrences,
    scheduleType: item.scheduleType,
    timezone: item.timezone,
    runAt: item.runAt,
    endsAt: item.endsAt,
    name: item.name,
    durationMs: item.durationMs,
    error: item.error,
    workflowName: item.workflowName,
    triggerType: item.triggerType,
  }
}

const EMPTY_ITEMS: ScheduledItem[] = []

export type ScheduleCoverage = "complete" | "truncated" | "unknown"

type LoadedSchedules = { items: ScheduledItem[]; coverage: ScheduleCoverage }

async function loadSchedules(options: UseSchedulesOptions): Promise<LoadedSchedules> {
  const preferUnified = options.preferUnifiedEndpoint !== false
  if (preferUnified) {
    try {
      const response = await schedulesApi.list({
        workflowId: options.workflowId,
        from: options.from,
        to: options.to,
        kinds: options.kinds,
      })
      return { items: response.items.map(mapApiItem), coverage: response.runsTruncated === true ? "truncated" : "complete" }
    } catch (error) {
      const status = error instanceof ApiError ? error.status : undefined
      if (status && status !== 404 && status !== 501) {
        throw error
      }
    }
  }

  const items = await aggregateSchedulesClientSide({
    listWorkflows: workflowsApi.list,
    listSchedules: workflowsApi.listSchedules,
    listRuns: runsApi.list,
    listJobs: trainingApi.listJobs,
    workflowId: options.workflowId,
  })
  // The fan-out reads at most 100 runs, so it cannot vouch for a whole month.
  return { items, coverage: "unknown" }
}

/**
 * Unified schedules hook — prefers `GET /api/schedules`, falls back to legacy fan-out.
 */
export function useSchedules(optionsOrWorkflowId?: string | UseSchedulesOptions): UseSchedulesResult {
  const options: UseSchedulesOptions =
    typeof optionsOrWorkflowId === "string"
      ? { workflowId: optionsOrWorkflowId }
      : optionsOrWorkflowId ?? {}

  const enabled = options.enabled !== false
  const key = enabled
    ? [
        "schedules",
        options.workflowId ?? "",
        options.from ?? "",
        options.to ?? "",
        (options.kinds ?? []).join(","),
        options.preferUnifiedEndpoint !== false ? "unified" : "legacy",
      ]
    : null

  const { data, error, isLoading, mutate } = useSWR<LoadedSchedules>(
    key,
    () => loadSchedules(options),
    { revalidateOnFocus: false, keepPreviousData: true },
  )

  const liveItems = data?.items ?? EMPTY_ITEMS

  return {
    items: liveItems,
    isLoading,
    error,
    isSample: false,
    coverage: data?.coverage ?? "unknown",
    refresh: () => {
      void mutate()
    },
  }
}
