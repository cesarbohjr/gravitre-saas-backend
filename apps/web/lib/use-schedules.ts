"use client"

import useSWR from "swr"

import { aggregateSchedulesClientSide } from "@/lib/schedules"
import { runsApi, schedulesApi, trainingApi, workflowsApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { SchedulesListParams, ScheduledItem } from "@/types/api"

export type UseSchedulesOptions = SchedulesListParams & {
  enabled?: boolean
  preferUnifiedEndpoint?: boolean
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
      return response.items
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

export function useSchedules(options: UseSchedulesOptions = {}) {
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
    { revalidateOnFocus: false },
  )

  return {
    items: data ?? [],
    error,
    isLoading,
    refresh: mutate,
  }
}
