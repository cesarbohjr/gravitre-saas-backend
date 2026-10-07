"use client"

/**
 * Shared reads for Intelligence › Data. SWR keys match the ones the training
 * workbench and the external dataset section already use, so a change made in
 * one place refreshes every view of the same list.
 */
import useSWR, { useSWRConfig } from "swr"
import { agentsApi, intelligenceApi, mlModelsApi, trainingApi } from "@/lib/api"

export const DATA_KEYS = {
  datasets: "training/datasets",
  jobs: "training/jobs",
  fineTuned: "training/fine-tuned-models",
  mlModels: "ml-models-list-studio",
  agents: "external-dataset-target-agents",
  providers: "external-dataset-providers-studio",
  references: "external-dataset-references-studio",
  knowledgeGraph: "intelligence/overview/knowledge-graph",
} as const

const once = { revalidateOnFocus: false }

export function useDataSources(enabled: boolean) {
  const datasets = useSWR(enabled ? DATA_KEYS.datasets : null, () => trainingApi.listDatasets(), once)
  const jobs = useSWR(enabled ? DATA_KEYS.jobs : null, () => trainingApi.listJobs(), once)
  const fineTuned = useSWR(enabled ? DATA_KEYS.fineTuned : null, () => trainingApi.listFineTunedModels(), once)
  const mlModels = useSWR(enabled ? DATA_KEYS.mlModels : null, () => mlModelsApi.list(), once)
  const agents = useSWR(enabled ? DATA_KEYS.agents : null, () => agentsApi.list(), once)
  const providers = useSWR(
    enabled ? DATA_KEYS.providers : null,
    () => trainingApi.listExternalDatasetProviders(),
    once,
  )
  const references = useSWR(
    enabled ? DATA_KEYS.references : null,
    () => trainingApi.listExternalDatasetReferences(),
    once,
  )
  const knowledgeGraph = useSWR(
    enabled ? DATA_KEYS.knowledgeGraph : null,
    () => intelligenceApi.knowledgeGraph(),
    once,
  )
  return { datasets, jobs, fineTuned, mlModels, agents, providers, references, knowledgeGraph }
}

export type DataSources = ReturnType<typeof useDataSources>

/** Refresh the lists a dataset change can affect. */
export function useRefreshDatasets() {
  const { mutate } = useSWRConfig()
  return () =>
    Promise.allSettled([
      mutate(DATA_KEYS.datasets),
      mutate(DATA_KEYS.references),
      mutate(DATA_KEYS.jobs),
    ])
}
