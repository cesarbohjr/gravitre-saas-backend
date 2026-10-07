"use client"

/**
 * Public dataset search (Hugging Face, Kaggle and any provider the backend
 * registers) plus the saved references list. Lives on Intelligence › Data and
 * inside Model Studio's Train step; both mount this one component.
 */
import { useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { Button } from "@/components/ui/button"
import { agentsApi, mlModelsApi, playsApi, trainingApi, workflowsApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type ExternalDatasetPurpose =
  | "reference"
  | "benchmark"
  | "runtime_retrieval"
  | "rag"
  | "evaluation"
  | "testing"
  | "fine_tuning"
  | "training"
  | "synthetic"
  | "agent_benchmarking"

type ExternalDatasetTargetType =
  | "agent"
  | "model"
  | "department"
  | "evaluation"
  | "play"
  | "workflow"

const EXTERNAL_DATASET_PURPOSES: Array<{ value: ExternalDatasetPurpose; label: string }> = [
  { value: "reference", label: "Reference" },
  { value: "benchmark", label: "Benchmark" },
  { value: "runtime_retrieval", label: "Runtime retrieval" },
  { value: "rag", label: "RAG" },
  { value: "evaluation", label: "Evaluation" },
  { value: "testing", label: "Testing" },
  { value: "fine_tuning", label: "Fine-tuning" },
  { value: "training", label: "Training" },
  { value: "synthetic", label: "Synthetic" },
  { value: "agent_benchmarking", label: "Agent benchmarking" },
]

const EXTERNAL_DATASET_TARGETS: Array<{ value: ExternalDatasetTargetType; label: string }> = [
  { value: "agent", label: "Agent" },
  { value: "model", label: "Model" },
  { value: "department", label: "Department" },
  { value: "evaluation", label: "Evaluation" },
  { value: "play", label: "Play" },
  { value: "workflow", label: "Workflow" },
]

export function ExternalDatasetsSection({
  enabled,
  source,
  onSavingChange,
  showHeading = true,
}: {
  enabled: boolean
  /** Off when the host page already titles this section. */
  showHeading?: boolean
  /** Recorded on the saved reference so the backend knows which surface added it. */
  source: "model_studio" | "intelligence_data"
  onSavingChange?: (saving: boolean) => void
}) {
  const referenceLock = useRef(false)
  const [externalQuery, setExternalQuery] = useState("")
  const [externalSearchTerm, setExternalSearchTerm] = useState("")
  const [externalProvider, setExternalProvider] = useState("")
  const [datasetInspectorOpen, setDatasetInspectorOpen] = useState(false)
  const [selectedExternalDatasetId, setSelectedExternalDatasetId] = useState("")
  const [externalPurpose, setExternalPurpose] = useState<ExternalDatasetPurpose>("training")
  const [externalTargetType, setExternalTargetType] = useState<ExternalDatasetTargetType>("model")
  const [externalTargetId, setExternalTargetId] = useState("")
  const [externalReferenceSaving, setSaving] = useState(false)
  const [externalReferenceError, setExternalReferenceError] = useState<string | null>(null)
  const [externalReferenceSaved, setExternalReferenceSaved] = useState<string | null>(null)
  function setExternalReferenceSaving(saving: boolean) {
    setSaving(saving)
    onSavingChange?.(saving)
  }

  const { data: modelsData, isLoading: modelsLoading, error: modelsError, mutate: mutateModels } = useSWR(
    enabled && externalTargetType === "model" ? "ml-models-list-studio" : null,
    () => mlModelsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalAgentsData, error: agentsError, isLoading: agentsLoading, mutate: mutateAgents } = useSWR(
    enabled &&
      (externalTargetType === "agent" || externalTargetType === "department")
      ? "external-dataset-target-agents"
      : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalWorkflowsData, error: workflowsError, isLoading: workflowsLoading, mutate: mutateWorkflows } = useSWR(
    enabled && externalTargetType === "workflow"
      ? "external-dataset-target-workflows"
      : null,
    () => workflowsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalPlaysData, error: playsError, isLoading: playsLoading, mutate: mutatePlays } = useSWR(
    enabled && externalTargetType === "play"
      ? "external-dataset-target-plays"
      : null,
    () => playsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalProvidersData, isLoading: providersLoading, error: providersError, mutate: mutateProviders } = useSWR(
    enabled ? "external-dataset-providers-studio" : null,
    () => trainingApi.listExternalDatasetProviders(),
    { revalidateOnFocus: false },
  )
  const externalProviders = externalProvidersData?.providers ?? []
  const externalProviderId = externalProvider || externalProviders[0]?.id || ""
  const externalProviderLabel =
    externalProviders.find((provider) => provider.id === externalProviderId)?.label ||
    "external provider"
  const { data: externalSearchData, isLoading: externalSearchLoading, error: externalSearchError, mutate: mutateExternalSearch } = useSWR(
    enabled && externalProviderId && externalSearchTerm
      ? ["external-dataset-search", externalProviderId, externalSearchTerm]
      : null,
    () => trainingApi.searchExternalDatasets(externalProviderId, externalSearchTerm, 12),
    { revalidateOnFocus: false },
  )
  const {
    data: externalInspectData,
    isLoading: externalInspectLoading,
    error: externalInspectError,
    mutate: mutateExternalInspect,
  } = useSWR(
    enabled && externalProviderId && selectedExternalDatasetId
      ? ["external-dataset-inspect", externalProviderId, selectedExternalDatasetId]
      : null,
    () => trainingApi.inspectExternalDataset(externalProviderId, selectedExternalDatasetId),
    { revalidateOnFocus: false },
  )
  const {
    data: externalReferencesData,
    error: referencesError,
    isLoading: referencesLoading,
    mutate: mutateExternalReferences,
  } = useSWR(
    enabled ? "external-dataset-references-studio" : null,
    () => trainingApi.listExternalDatasetReferences(),
    { revalidateOnFocus: false },
  )

  const externalDatasets = externalSearchData?.datasets ?? []
  const selectedExternalDataset = externalInspectData?.dataset ?? null
  const externalReferences = externalReferencesData?.references ?? []
  const externalTargetOptions = useMemo(() => {
    if (externalTargetType === "agent") {
      return (externalAgentsData?.agents ?? []).map((agent) => ({
        id: agent.id,
        label: agent.name || agent.role || agent.id,
      }))
    }
    if (externalTargetType === "model") {
      return (modelsData?.models ?? []).map((model) => ({
        id: model.id,
        label: model.name || model.id,
      }))
    }
    if (externalTargetType === "workflow") {
      return (externalWorkflowsData?.workflows ?? []).map((workflow) => ({
        id: workflow.id,
        label: workflow.name || workflow.id,
      }))
    }
    if (externalTargetType === "play") {
      return (externalPlaysData?.plays ?? []).map((item) => ({
        id: item.play.key,
        label: item.play.name || item.play.key,
      }))
    }
    if (externalTargetType === "department") {
      const departments = new Set(
        (externalAgentsData?.agents ?? [])
          .map((agent) => String(agent.department || "").trim())
          .filter(Boolean),
      )
      return Array.from(departments).sort().map((department) => ({
        id: department,
        label: department,
      }))
    }
    return []
  }, [
    externalTargetType,
    externalAgentsData,
    externalWorkflowsData,
    externalPlaysData,
    modelsData,
  ])

  const targetLoad = externalTargetType === "model"
    ? { error: modelsError, loading: modelsLoading, retry: mutateModels }
    : externalTargetType === "agent" || externalTargetType === "department"
      ? { error: agentsError, loading: agentsLoading, retry: mutateAgents }
      : externalTargetType === "workflow"
        ? { error: workflowsError, loading: workflowsLoading, retry: mutateWorkflows }
        : externalTargetType === "play"
          ? { error: playsError, loading: playsLoading, retry: mutatePlays }
          : { error: null, loading: false, retry: () => Promise.resolve() }
  const targetReady = externalTargetType === "evaluation"
    ? Boolean(externalTargetId.trim())
    : !targetLoad.error && !targetLoad.loading && externalTargetOptions.some(option => option.id === externalTargetId)

  async function saveExternalDatasetReference() {
    if (referenceLock.current || !externalProviderId || !selectedExternalDatasetId || !selectedExternalDataset || externalInspectError || !targetReady) return
    referenceLock.current = true
    setExternalReferenceSaving(true)
    setExternalReferenceError(null)
    setExternalReferenceSaved(null)
    try {
      const saved = await trainingApi.createExternalDatasetReference({
        provider: externalProviderId,
        datasetId: selectedExternalDatasetId,
        purpose: externalPurpose,
        targetType: externalTargetType,
        targetId: externalTargetId.trim(),
        accessMode: "reference",
        metadata: { source },
      })
      if (!saved.id) throw new Error("The server did not confirm a saved reference. Your selection is retained.")
      setExternalReferenceSaved(`Reference saved for ${externalTargetType} ${externalTargetId.trim()}. This save does not import or index provider files.`)
      // Refresh failure must not turn an acknowledged save into a failed mutation.
      void Promise.allSettled([mutateExternalReferences()])
    } catch (error) {
      setExternalReferenceError(
        error instanceof Error ? error.message : "Could not add the dataset reference.",
      )
    } finally {
      referenceLock.current = false
      setExternalReferenceSaving(false)
    }
  }

  return (
    <section className="border-y border-divide" aria-labelledby="external-dataset-connectors">
      <div className="flex flex-col gap-2 border-b border-divide px-3 py-3 sm:flex-row sm:items-end sm:justify-between">
        <div className={showHeading ? undefined : "sr-only"}>
          <p id="external-dataset-connectors" className="text-sm font-medium text-foreground">
            External datasets
          </p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Search provider metadata, review access and purpose, then choose where to use it.
          </p>
        </div>
        <span className="font-mono text-[10px] text-muted-foreground">
          {providersError ? "Providers unavailable" : externalProviders.length > 0 ? externalProviders.map((p) => p.label).join(" · ") : providersLoading ? "Loading providers…" : "No providers returned"}
        </span>
      </div>
      <form
        className="grid gap-2 px-3 py-3 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault()
          setExternalSearchTerm(externalQuery.trim())
        }}
      >
        {externalProviders.length > 1 ? (
          <select
            disabled={externalReferenceSaving}
            value={externalProviderId}
            onChange={(event) => {
              setExternalProvider(event.target.value)
              setExternalSearchTerm("")
              setSelectedExternalDatasetId("")
              setDatasetInspectorOpen(false)
              setExternalReferenceError(null)
              setExternalReferenceSaved(null)
            }}
            aria-label="Dataset provider"
            className="min-h-11 border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
          >
            {externalProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.label}
              </option>
            ))}
          </select>
        ) : null}
        <input
          disabled={externalReferenceSaving}
          value={externalQuery}
          onChange={(event) => setExternalQuery(event.target.value)}
          placeholder={`Search ${externalProviderLabel} datasets`}
          aria-label="Search datasets"
          className="min-h-11 min-w-0 border border-divide bg-transparent px-3 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
        />
        <Button
          type="submit"
          variant="outline"
          disabled={!externalQuery.trim() || !externalProviderId || externalReferenceSaving}
        >
          Search
        </Button>
      </form>
      {providersError || externalSearchError ? (
        <WorkSectionErrorCard
          title={providersError ? "Could not load dataset providers" : "Could not search datasets"}
          message="Try again to browse provider metadata."
          onRetry={() => { void mutateProviders(); void mutateExternalSearch() }}
        />
      ) : externalSearchLoading ? (
        <p className="px-3 pb-3 text-sm text-muted-foreground">Searching provider metadata…</p>
      ) : externalSearchTerm && externalDatasets.length === 0 ? (
        <p className="px-3 pb-3 text-sm text-muted-foreground">No matching datasets.</p>
      ) : externalDatasets.length > 0 ? (
        <ul className="divide-y divide-divide border-t border-divide">
          {externalDatasets.map((dataset) => {
            const restricted = dataset.gated || dataset.private
            const selected = selectedExternalDatasetId === dataset.dataset_id
            return (
              <li key={dataset.dataset_id}>
                <button
                  type="button"
                  disabled={restricted || externalReferenceSaving}
                  aria-pressed={selected}
                  onClick={() => {
                    setSelectedExternalDatasetId(dataset.dataset_id)
                    setDatasetInspectorOpen(true)
                    setExternalReferenceError(null)
                    setExternalReferenceSaved(null)
                  }}
                  className={cn(
                    "grid w-full gap-1 px-3 py-2.5 text-left sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4",
                    restricted
                      ? "cursor-not-allowed opacity-60"
                      : selected
                        ? "bg-[color:var(--g-surface-2)]"
                        : "hover:bg-[color:var(--g-surface-2)]/50",
                  )}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">{dataset.dataset_id}</p>
                    <p className={cn(TYPE.meta, "mt-0.5 line-clamp-1")}>
                      {restricted
                        ? "Restricted dataset — authorization required"
                        : dataset.description || "Public dataset"}
                    </p>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {restricted ? "RESTRICTED" : "PREVIEW"}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}

      {selectedExternalDatasetId ? (
        <SelectionInspector
          open={datasetInspectorOpen}
          pending={externalReferenceSaving}
          onOpenChange={open => { if (!referenceLock.current) setDatasetInspectorOpen(open) }}
          title={selectedExternalDatasetId}
          description={externalReferenceSaving ? "Saving this reference. Your review stays open until the request returns." : "Review provider metadata and choose where to use this dataset."}
          className="border-t border-divide px-3 py-3"
        >
        <div data-review-surface="external-dataset-inspect">
          {externalInspectError ? (
            <WorkSectionErrorCard title="Could not load dataset preview" message="Retry before using this dataset." onRetry={() => void mutateExternalInspect()} />
          ) : externalInspectLoading ? (
            <p className="text-sm text-muted-foreground">Loading dataset preview…</p>
          ) : selectedExternalDataset ? (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-foreground">{selectedExternalDataset.dataset_id}</p>
                  <p className={cn(TYPE.meta, "mt-0.5")}>
                    {selectedExternalDataset.description || "Dataset preview"}
                  </p>
                  <p className={cn(TYPE.meta, "mt-1")}>
                    {selectedExternalDataset.fileCount == null ? "File count not reported" : `${selectedExternalDataset.fileCount} files`} · provider: {externalProviderLabel}
                  </p>
                </div>
                <span className="font-mono text-[10px] text-muted-foreground">PREVIEW</span>
              </div>

              <div className="grid gap-2 xl:grid-cols-3">
                <label className="space-y-1">
                  <span className={TYPE.meta}>Purpose</span>
                  <select
                    disabled={externalReferenceSaving}
                    value={externalPurpose}
                    onChange={(event) => { setExternalPurpose(event.target.value as ExternalDatasetPurpose); setExternalReferenceSaved(null); setExternalReferenceError(null) }}
                    className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                  >
                    {EXTERNAL_DATASET_PURPOSES.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className={TYPE.meta}>Use with</span>
                  <select
                    disabled={externalReferenceSaving}
                    value={externalTargetType}
                    onChange={(event) => {
                      setExternalTargetType(event.target.value as ExternalDatasetTargetType)
                      setExternalTargetId("")
                      setExternalReferenceError(null)
                      setExternalReferenceSaved(null)
                    }}
                    className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                  >
                    {EXTERNAL_DATASET_TARGETS.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </label>
                <label className="space-y-1">
                  <span className={TYPE.meta}>
                    {externalTargetType === "evaluation" ? "Evaluation ID" : `Existing ${externalTargetType}`}
                  </span>
                  {externalTargetType === "evaluation" ? (
                    <input
                      disabled={externalReferenceSaving}
                      value={externalTargetId}
                      onChange={(event) => { setExternalTargetId(event.target.value); setExternalReferenceSaved(null); setExternalReferenceError(null) }}
                      placeholder="Existing evaluation ID"
                      className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                    />
                  ) : (
                    <select
                      value={externalTargetId}
                      onChange={(event) => { setExternalTargetId(event.target.value); setExternalReferenceSaved(null); setExternalReferenceError(null) }}
                      disabled={externalReferenceSaving || targetLoad.loading || Boolean(targetLoad.error)}
                      aria-label="Dataset target"
                      className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                    >
                      <option value="">{targetLoad.loading ? "Loading targets…" : targetLoad.error ? "Targets unavailable" : "Select an existing target"}</option>
                      {externalTargetOptions.map((option) => (
                        <option key={option.id} value={option.id}>{option.label}</option>
                      ))}
                    </select>
                  )}
                </label>
              </div>

              {targetLoad.error ? (
                <WorkSectionErrorCard title="Could not load dataset targets" message="Your dataset and purpose are retained. Retry before choosing existing work." onRetry={() => void targetLoad.retry()} />
              ) : externalTargetType !== "evaluation" && !targetLoad.loading && externalTargetOptions.length === 0 ? (
                <p className={TYPE.meta}>No existing {externalTargetType} targets were returned. Choose another target type or create the target in its workspace first.</p>
              ) : null}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  className="min-h-11"
                  disabled={!targetReady || externalReferenceSaving || Boolean(externalInspectError)}
                  onClick={() => void saveExternalDatasetReference()}
                >
                  {externalReferenceSaving ? "Saving reference…" : "Save dataset reference"}
                </Button>
                <p className={TYPE.meta}>
                  Adds a reusable dataset reference to Gravitre. Provider files are only imported when a supported materialization step is explicitly started.
                </p>
              </div>
              {externalReferenceError ? (
                <p role="alert" className="text-sm text-destructive">{externalReferenceError}</p>
              ) : null}
              {externalReferenceSaved ? (
                <p role="status" className="text-sm text-[color:var(--g-brand-active)]">{externalReferenceSaved}</p>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Dataset preview is unavailable.</p>
          )}
        </div>
        </SelectionInspector>
      ) : null}

      <section aria-label="Saved dataset references" className="border-t border-divide px-3 py-3">
        <p className={TYPE.eyebrow}>Saved references</p>
        {referencesError ? <WorkSectionErrorCard title="Could not refresh saved references" message="An acknowledged save is retained. Retry to inspect the workspace list." onRetry={() => void mutateExternalReferences()} /> : null}
        {referencesLoading && !externalReferencesData ? <p className={TYPE.meta}>Loading saved references…</p> : Array.isArray(externalReferencesData?.references) && !referencesError && externalReferences.length === 0 ? <p className={TYPE.meta}>No saved references returned.</p> : null}
        {!referencesLoading && !referencesError && !Array.isArray(externalReferencesData?.references) ? <p className={TYPE.meta}>Saved references not reported.</p> : null}
        <ul className="mt-2 divide-y divide-divide">
          {externalReferences.map(reference => (
            <li key={reference.id} className="min-w-0 py-2">
              <p className="break-all text-sm font-medium">{reference.external_dataset_id}</p>
              <p className={cn(TYPE.meta, "break-words")}>{reference.purpose} · {reference.target_type} · {reference.target_id}</p>
              <p className={TYPE.meta}>{reference.provider} · {reference.access_mode === "reference" ? "Reference metadata; no import or indexing confirmed" : `${reference.access_mode} access requested; materialization not reported here`}</p>
            </li>
          ))}
        </ul>
      </section>
      {externalReferences.length > 0 ? (
        <div className="border-t border-divide px-3 py-2">
          <p className={TYPE.meta}>
            {externalReferences.length} reusable dataset{externalReferences.length === 1 ? "" : "s"} added to this workspace.
          </p>
        </div>
      ) : null}
    </section>
  )
}
