"use client"

/**
 * Models v2 — one place that loads every real source the Models page needs:
 * the registry list, each model's versions + metrics, training jobs (retrain
 * state) and dataset names (lineage "Learns from").
 */
import { useCallback, useMemo } from "react"
import useSWR from "swr"
import { mlModelsApi, trainingApi } from "@/lib/api"
import type { MlModelDetail } from "@/types/api"

export function useModelsData(enabled: boolean) {
  const list = useSWR(enabled ? "ml-models-list" : null, () => mlModelsApi.list())
  const models = useMemo(() => list.data?.models ?? [], [list.data])
  const ids = useMemo(() => models.map((m) => m.id).sort().join(","), [models])

  const details = useSWR(
    enabled && ids ? ["ml-models-details", ids] : null,
    async () => {
      const settled = await Promise.allSettled(models.map((m) => mlModelsApi.get(m.id)))
      const out: Record<string, MlModelDetail> = {}
      settled.forEach((row, index) => {
        if (row.status === "fulfilled") out[models[index].id] = row.value
      })
      return out
    },
    { revalidateOnFocus: false },
  )

  // Same SWR keys as Model Studio so the cache is shared.
  const jobs = useSWR(enabled ? "training-jobs-studio" : null, () => trainingApi.listJobs(), {
    revalidateOnFocus: false,
  })
  const datasets = useSWR(enabled ? "training-datasets-studio" : null, () => trainingApi.listDatasets(), {
    revalidateOnFocus: false,
  })

  const datasetNames = useMemo(() => {
    const map: Record<string, string> = {}
    for (const row of datasets.data?.datasets ?? []) map[row.id] = row.name
    return map
  }, [datasets.data])

  const { mutate: mutateList } = list
  const { mutate: mutateDetails } = details
  const { mutate: mutateJobs } = jobs
  const { mutate: mutateDatasets } = datasets
  const refresh = useCallback(async () => {
    await Promise.all([mutateList(), mutateDetails(), mutateJobs(), mutateDatasets()])
  }, [mutateList, mutateDetails, mutateJobs, mutateDatasets])

  return {
    models,
    details: details.data ?? {},
    detailsLoading: details.isLoading,
    jobs: jobs.data?.jobs ?? [],
    datasetNames,
    isLoading: list.isLoading,
    isValidating: list.isValidating || details.isValidating || jobs.isValidating,
    error: list.error as unknown,
    refresh,
    mutateJobs,
    mutateList,
  }
}
