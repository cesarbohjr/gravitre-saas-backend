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
  }
}

async function loadSchedules(options: UseSchedulesOptions): Promise<ScheduledItem[]> {
  const preferUnified = options.preferUnifiedEndpoint !== false
  if (preferUnified) {
    try {
      const response = await schedulesApi.list({
        workflowId: options.workflowId,
        from: options.from,
        to: options.to,
        kinds: options.kinds,
      })
      return response.items.map(mapApiItem)
    } catch (error) {
      const status = error instanceof ApiError ? error.status : undefined
      if (status && status !== 404 && status !== 501) {
        throw error
      }
    }
  }

  return aggregateSchedulesClientSide({
    listWorkflows: workflowsApi.list,
    listSchedules: workflowsApi.listSchedules,
    listRuns: runsApi.list,
    listJobs: trainingApi.listJobs,
    workflowId: options.workflowId,
  })
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

  const { data, error, isLoading, mutate } = useSWR<ScheduledItem[]>(
    key,
    () => loadSchedules(options),
    { revalidateOnFocus: false, keepPreviousData: true },
  )

  const liveItems = data ?? []

  return {
    items: liveItems,
    isLoading,
    error,
    isSample: false,
    refresh: () => {
      void mutate()
    },
  }
}
