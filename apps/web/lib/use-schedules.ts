"use client"

import useSWR from "swr"
import { runsApi, trainingApi, workflowsApi } from "@/lib/api"
import {
  fromRun,
  fromTrainingJob,
  fromWorkflowSchedule,
  sampleScheduledItems,
  type ScheduledItem,
} from "@/lib/schedules"

export interface UseSchedulesResult {
  items: ScheduledItem[]
  isLoading: boolean
  error: unknown
  /** True when the displayed data is sample fallback, not live backend data. */
  isSample: boolean
  refresh: () => void
}

/**
 * Aggregate workflow schedules, task runs and training jobs into a single
 * unified list of ScheduledItem.
 *
 * NOTE: There is no backend endpoint that returns all schedules at once yet,
 * so this composes results from multiple endpoints client-side (workflow
 * schedules are an N+1 fetch across workflows). When the backend ships a
 * unified `GET /api/schedules` endpoint, swap this fetcher to call it directly.
 *
 * @param workflowId Optional filter — only aggregate a single workflow's data.
 */
export function useSchedules(workflowId?: string): UseSchedulesResult {
  const key = workflowId ? ["schedules", workflowId] : ["schedules", "all"]

  const { data, error, isLoading, mutate } = useSWR(
    key,
    async (): Promise<ScheduledItem[]> => {
      const items: ScheduledItem[] = []

      // 1) Workflow schedules
      try {
        let workflows: { id: string; name: string }[] = []
        if (workflowId) {
          const wf = await workflowsApi.get(workflowId).catch(() => null)
          workflows = wf ? [{ id: wf.id, name: wf.name }] : [{ id: workflowId, name: "Workflow" }]
        } else {
          const res = await workflowsApi.list()
          workflows = (res.workflows ?? []).map((w) => ({ id: w.id, name: w.name }))
        }

        const scheduleResults = await Promise.all(
          workflows.map(async (wf) => {
            try {
              const res = await workflowsApi.listSchedules(wf.id)
              return (res.schedules ?? []).map((s) => fromWorkflowSchedule(s, wf.name))
            } catch {
              return []
            }
          }),
        )
        for (const group of scheduleResults) items.push(...group)
      } catch {
        // ignore — covered by fallback below
      }

      // 2) Task runs
      try {
        const res = await runsApi.list(
          workflowId ? { workflow_id: workflowId, limit: 100 } : { limit: 100 },
        )
        for (const run of res.runs ?? []) items.push(fromRun(run))
      } catch {
        // ignore
      }

      // 3) Training jobs (org-wide; not workflow-scoped)
      if (!workflowId) {
        try {
          const res = await trainingApi.listJobs()
          for (const job of res.jobs ?? []) items.push(fromTrainingJob(job))
        } catch {
          // ignore
        }
      }

      return items
    },
    { revalidateOnFocus: false, keepPreviousData: true },
  )

  const liveItems = data ?? []
  const isSample = !isLoading && liveItems.length === 0
  const items = isSample ? sampleScheduledItems() : liveItems

  return {
    items,
    isLoading,
    error,
    isSample,
    refresh: () => {
      void mutate()
    },
  }
}
