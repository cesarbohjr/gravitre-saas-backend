"use client"

/**
 * I8 — Model Studio: Create · Train · Evaluate · Deploy · Runs with intent-first create.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { useIsMobile } from "@/hooks/use-mobile"
import { Button } from "@/components/ui/button"
import { agentsApi, mlModelsApi, playsApi, trainingApi, workflowsApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  STUDIO_INTENTS,
  STUDIO_SEGMENTS,
  formatModelCatalogRow,
  type StudioIntentId,
  type StudioSegment,
} from "@/lib/intelligence/model-catalog-display"
import { describeStatus } from "@/lib/intelligence/status-language"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight } from "@phosphor-icons/react"

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

export function ModelStudioStage({
  enabled,
  suggestedQuestions,
}: {
  enabled: boolean
  suggestedQuestions?: string[]
}) {
  const router = useRouter()
  const [segment, setSegment] = useState<StudioSegment>("create")
  const compactInspector = useIsMobile(1024)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [intent, setIntent] = useState<StudioIntentId | null>(null)
  const [externalQuery, setExternalQuery] = useState("")
  const [externalSearchTerm, setExternalSearchTerm] = useState("")
  const [externalProvider, setExternalProvider] = useState("")
  const [datasetInspectorOpen, setDatasetInspectorOpen] = useState(false)
  const [selectedExternalDatasetId, setSelectedExternalDatasetId] = useState("")
  const [externalPurpose, setExternalPurpose] = useState<ExternalDatasetPurpose>("training")
  const [externalTargetType, setExternalTargetType] = useState<ExternalDatasetTargetType>("model")
  const [externalTargetId, setExternalTargetId] = useState("")
  const [externalReferenceSaving, setExternalReferenceSaving] = useState(false)
  const [externalReferenceError, setExternalReferenceError] = useState<string | null>(null)
  const [externalReferenceSaved, setExternalReferenceSaved] = useState<string | null>(null)

  const { data: modelsData, isLoading: modelsLoading, error: modelsError, mutate: mutateModels } = useSWR(
    enabled &&
      (segment === "evaluate" ||
        segment === "deploy" ||
        (segment === "train" && externalTargetType === "model"))
      ? "ml-models-list-studio"
      : null,
    () => mlModelsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalAgentsData } = useSWR(
    enabled &&
      segment === "train" &&
      (externalTargetType === "agent" || externalTargetType === "department")
      ? "external-dataset-target-agents"
      : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalWorkflowsData } = useSWR(
    enabled && segment === "train" && externalTargetType === "workflow"
      ? "external-dataset-target-workflows"
      : null,
    () => workflowsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: externalPlaysData } = useSWR(
    enabled && segment === "train" && externalTargetType === "play"
      ? "external-dataset-target-plays"
      : null,
    () => playsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: jobsData, isLoading: jobsLoading, error: jobsError, mutate: mutateJobs } = useSWR(
    enabled && (segment === "train" || segment === "runs") ? "training-jobs-studio" : null,
    () => trainingApi.listJobs(),
    { revalidateOnFocus: false },
  )
  const { data: datasetsData, isLoading: datasetsLoading, error: datasetsError, mutate: mutateDatasets } = useSWR(
    enabled && segment === "train" ? "training-datasets-studio" : null,
    () => trainingApi.listDatasets(),
    { revalidateOnFocus: false },
  )
  const { data: externalProvidersData, isLoading: providersLoading, error: providersError, mutate: mutateProviders } = useSWR(
    enabled && segment === "train" ? "external-dataset-providers-studio" : null,
    () => trainingApi.listExternalDatasetProviders(),
    { revalidateOnFocus: false },
  )
  const externalProviders = externalProvidersData?.providers ?? []
  const externalProviderId = externalProvider || externalProviders[0]?.id || ""
  const externalProviderLabel =
    externalProviders.find((provider) => provider.id === externalProviderId)?.label ||
    "external provider"
  const { data: externalSearchData, isLoading: externalSearchLoading, error: externalSearchError, mutate: mutateExternalSearch } = useSWR(
    enabled && segment === "train" && externalProviderId && externalSearchTerm
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
    enabled && segment === "train" && externalProviderId && selectedExternalDatasetId
      ? ["external-dataset-inspect", externalProviderId, selectedExternalDatasetId]
      : null,
    () => trainingApi.inspectExternalDataset(externalProviderId, selectedExternalDatasetId),
    { revalidateOnFocus: false },
  )
  const {
    data: externalReferencesData,
    mutate: mutateExternalReferences,
  } = useSWR(
    enabled && segment === "train" ? "external-dataset-references-studio" : null,
    () => trainingApi.listExternalDatasetReferences(),
    { revalidateOnFocus: false },
  )

  const models = modelsData?.models ?? []
  const catalog = useMemo(() => models.map(formatModelCatalogRow), [models])
  const evaluateModels = catalog.filter((m) =>
    ["ready", "validating", "evaluating", "training"].includes(m.technicalStatus),
  )
  const deployModels = catalog.filter(
    (m) => m.technicalStatus === "ready" || m.technicalStatus === "deployed",
  )
  const jobs = jobsData?.jobs ?? []
  const datasets = datasetsData?.datasets ?? []
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

  function startCreate() {
    const params = new URLSearchParams({ action: "register" })
    if (intent) params.set("intent", intent)
    router.push(`${APP_ROUTES.models}?${params.toString()}`)
  }

  async function saveExternalDatasetReference() {
    if (!externalProviderId || !selectedExternalDatasetId || !externalTargetId.trim()) return
    setExternalReferenceSaving(true)
    setExternalReferenceError(null)
    setExternalReferenceSaved(null)
    try {
      await trainingApi.createExternalDatasetReference({
        provider: externalProviderId,
        datasetId: selectedExternalDatasetId,
        purpose: externalPurpose,
        targetType: externalTargetType,
        targetId: externalTargetId.trim(),
        accessMode: "reference",
        metadata: { source: "model_studio" },
      })
      await mutateExternalReferences()
      setExternalReferenceSaved("Dataset added to the selected target as a reusable provider reference.")
    } catch (error) {
      setExternalReferenceError(
        error instanceof Error ? error.message : "Could not add the dataset reference.",
      )
    } finally {
      setExternalReferenceSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {modelsError || jobsError || datasetsError ? (
        <WorkSectionErrorCard
          title="Could not load Model Studio"
          message={
            (modelsError instanceof Error && modelsError.message) ||
            (jobsError instanceof Error && jobsError.message) ||
            (datasetsError instanceof Error && datasetsError.message) ||
            "One of the Model Studio lists did not return."
          }
          onRetry={() => {
            void mutateModels()
            void mutateJobs()
            void mutateDatasets()
          }}
        />
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[184px_minmax(0,1fr)]">
        <div className="space-y-3 lg:border-r lg:border-[color:var(--g-border-subtle)] lg:pr-4">
          <p className={cn(TYPE.meta)}>
            Describe what the model should do, then train, evaluate, and deploy it.
          </p>
          <nav
            aria-label="Model Studio action"
            className="-mx-1 flex gap-1 overflow-x-auto lg:mx-0 lg:flex-col lg:gap-0 lg:overflow-visible"
          >
            {STUDIO_SEGMENTS.map((item, index) => {
              const active = segment === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => { setSegment(item.id); setInspectorOpen(false); setDatasetInspectorOpen(false) }}
                  aria-current={active ? "step" : undefined}
                  className={cn(
                    "flex min-h-11 shrink-0 items-baseline gap-2 border-b-2 px-2 py-1.5 text-left text-sm lg:border-b-0 lg:border-l-2 lg:py-2",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    active
                      ? "border-[color:var(--g-brand)] font-medium text-[color:var(--g-text-primary)]"
                      : "border-transparent text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
                  )}
                >
                  <span className="font-mono text-[11px] tabular-nums text-[color:var(--g-text-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {item.label}
                </button>
              )
            })}
          </nav>
        </div>

        <div className="min-w-0">
          {segment === "create" ? (
            <div className="space-y-4">
              <p className="text-sm text-foreground">What do you want this model to do?</p>
              <div className="flex flex-col border border-divide lg:flex-row">
                <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="studio-queue">
                  {STUDIO_INTENTS.map((item) => {
                    const selected = intent === item.id
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          onClick={() => { setIntent(item.id); setInspectorOpen(true) }}
                          aria-pressed={selected}
                          className={cn(
                            "min-h-11 w-full px-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
                            selected
                              ? "bg-[color:var(--g-surface-2)]"
                              : "hover:bg-[color:var(--g-surface-2)]/50",
                          )}
                        >
                          <p className="text-sm font-medium text-foreground">{item.label}</p>
                          <p className={cn(TYPE.meta, "mt-0.5")}>{item.description}</p>
                        </button>
                      </li>
                    )
                  })}
                </ul>
                {intent ? (
                  <SelectionInspector
                    open={inspectorOpen}
                    onOpenChange={setInspectorOpen}
                    title={STUDIO_INTENTS.find((item) => item.id === intent)?.label ?? "Model intent"}
                    description="Review the model's purpose before registering it."
                    className="flex-1 border-l border-divide p-4"
                  >
                    <div data-review-surface="studio-inspect">
                    <p className={TYPE.eyebrow}>Intent</p>
                    <p className="mt-1 text-sm font-medium text-foreground">
                      {STUDIO_INTENTS.find((item) => item.id === intent)?.label}
                    </p>
                    <p className={cn(TYPE.meta, "mt-1")}>
                      {STUDIO_INTENTS.find((item) => item.id === intent)?.description}
                    </p>
                    {compactInspector ? (
                      <Button className="mt-6 min-h-11 w-full gap-1.5" onClick={() => { setInspectorOpen(false); startCreate() }}>
                        Continue to register <ArrowRight className="h-4 w-4" aria-hidden />
                      </Button>
                    ) : null}
                    </div>
                  </SelectionInspector>
                ) : (
                  <p className="sr-only">Select an intent — inspector stays closed until then.</p>
                )}
              </div>
              <Button
                onClick={() => compactInspector ? setInspectorOpen(true) : startCreate()}
                disabled={!intent}
                className="min-h-11 gap-1.5"
              >
                {compactInspector ? "Review selected intent" : "Continue to register"}
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </div>
          ) : null}

          {segment === "train" ? (
            <div className="space-y-4">
              <section className="border-y border-divide" aria-labelledby="dataset-picker">
                <div className="flex flex-col gap-2 border-b border-divide px-3 py-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p id="external-dataset-connectors" className="text-sm font-medium text-foreground">
                      External dataset connectors
                    </p>
                    <p className={cn(TYPE.meta, "mt-0.5")}>
                      Browse free dataset providers, preview a dataset, then add it to your model.
                    </p>
                  </div>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {externalProviders.length > 0 ? externalProviders.map((p) => p.label).join(" · ") : providersLoading ? "Loading providers…" : "No providers available"}
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
                    value={externalQuery}
                    onChange={(event) => setExternalQuery(event.target.value)}
                    placeholder={`Search ${externalProviderLabel} datasets`}
                    aria-label="Search datasets"
                    className="min-h-11 min-w-0 border border-divide bg-transparent px-3 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                  />
                  <Button
                    type="submit"
                    variant="outline"
                    disabled={!externalQuery.trim() || !externalProviderId}
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
                            disabled={restricted}
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
                    onOpenChange={setDatasetInspectorOpen}
                    title={selectedExternalDatasetId}
                    description="Review provider metadata and choose where to use this dataset."
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
                              value={externalPurpose}
                              onChange={(event) => setExternalPurpose(event.target.value as ExternalDatasetPurpose)}
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
                              {externalTargetType === "evaluation" ? "Evaluation ID" : "Canonical target"}
                            </span>
                            {externalTargetType === "evaluation" ? (
                              <input
                                value={externalTargetId}
                                onChange={(event) => setExternalTargetId(event.target.value)}
                                placeholder="Existing evaluation ID"
                                className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                              />
                            ) : (
                              <select
                                value={externalTargetId}
                                onChange={(event) => setExternalTargetId(event.target.value)}
                                aria-label="Canonical dataset target"
                                className="min-h-11 w-full border border-divide bg-transparent px-2 py-2 text-sm outline-none focus:border-[color:var(--g-brand)]"
                              >
                                <option value="">Select an existing target</option>
                                {externalTargetOptions.map((option) => (
                                  <option key={option.id} value={option.id}>{option.label}</option>
                                ))}
                              </select>
                            )}
                          </label>
                        </div>

                        <div className="flex flex-wrap items-center gap-3">
                          <Button
                            type="button"
                            variant="outline"
                            className="min-h-11"
                            disabled={!externalTargetId.trim() || externalReferenceSaving}
                            onClick={() => void saveExternalDatasetReference()}
                          >
                            {externalReferenceSaving ? "Adding dataset…" : "Use dataset"}
                          </Button>
                          <p className={TYPE.meta}>
                            Adds a reusable dataset reference to Gravitre. Provider files are only imported when a supported materialization step is explicitly started.
                          </p>
                        </div>
                        {externalReferenceError ? (
                          <p className="text-sm text-destructive">{externalReferenceError}</p>
                        ) : null}
                        {externalReferenceSaved ? (
                          <p className="text-sm text-[color:var(--g-brand-active)]">{externalReferenceSaved}</p>
                        ) : null}
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">Dataset preview is unavailable.</p>
                    )}
                  </div>
                  </SelectionInspector>
                ) : null}

                {externalReferences.length > 0 ? (
                  <div className="border-t border-divide px-3 py-2">
                    <p className={TYPE.meta}>
                      {externalReferences.length} reusable dataset{externalReferences.length === 1 ? "" : "s"} added to this workspace.
                    </p>
                  </div>
                ) : null}
              </section>
              {datasetsError && datasets.length === 0 ? null : datasetsLoading ? (
                <p className="text-sm text-muted-foreground">Loading datasets…</p>
              ) : datasets.length === 0 ? (
                <EmptyState
                  title="Upload your own training data"
                  description="Create or upload a private dataset for training. Free public datasets from Hugging Face and Kaggle can be added above."
                  action={{
                    label: "Create or upload dataset",
                    onClick: () => {
                      window.location.href = APP_ROUTES.training
                    },
                  }}
                />
              ) : (
                <ul className="divide-y divide-divide border border-divide">
                  {datasets.slice(0, 8).map((dataset) => (
                    <li key={dataset.id} className="px-3 py-2 text-sm">
                      {dataset.name}
                    </li>
                  ))}
                </ul>
              )}
              <Link
                href={APP_ROUTES.training}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]"
              >
                Manage datasets and training runs
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          ) : null}

          {segment === "evaluate" ? (
            <div className="space-y-3">
              {modelsError && models.length === 0 ? null : modelsLoading ? (
                <p className="text-sm text-muted-foreground">Loading models…</p>
              ) : evaluateModels.length === 0 ? (
                <EmptyState
                  title="Nothing to evaluate yet"
                  description="Models in training or ready-to-review appear here from the live registry."
                />
              ) : (
                evaluateModels.map((model) => (
                  <Link
                    key={model.id}
                    href={model.href}
                    className="block border-b border-divide px-3 py-2 last:border-b-0"
                  >
                    <p className="text-sm font-medium">{model.name}</p>
                    <p className={TYPE.meta}>{model.businessStatus}</p>
                  </Link>
                ))
              )}
            </div>
          ) : null}

          {segment === "deploy" ? (
            <div className="space-y-3">
              {modelsError && models.length === 0 ? null : modelsLoading ? (
                <p className="text-sm text-muted-foreground">Loading models…</p>
              ) : deployModels.length === 0 ? (
                <EmptyState
                  title="No models ready to deploy"
                  description="Ready and live models from the registry appear here. Deploy happens on the model page."
                />
              ) : (
                deployModels.map((model) => (
                  <Link
                    key={model.id}
                    href={model.href}
                    className="block border-b border-divide px-3 py-2 last:border-b-0"
                  >
                    <p className="text-sm font-medium">{model.name}</p>
                    <p className={TYPE.meta}>
                      {model.businessStatus} · {model.whereUsed}
                    </p>
                  </Link>
                ))
              )}
            </div>
          ) : null}

          {segment === "runs" ? (
            <div className="space-y-3">
              {jobsError && jobs.length === 0 ? null : jobsLoading ? (
                <p className="text-sm text-muted-foreground">Loading runs…</p>
              ) : jobs.length === 0 ? (
                <EmptyState
                  title="No training runs yet"
                  description="Runs are the same jobs as /training — shown here so Training is not a hub tab."
                />
              ) : (
                jobs.slice(0, 12).map((job) => {
                  const status = describeStatus(job.status)
                  return (
                    <div key={job.id} className="border-b border-divide px-3 py-2 last:border-b-0">
                      <p className="text-sm font-medium">{job.dataset_name || job.model_base}</p>
                      <p className={TYPE.meta}>
                        {status.phrase} · {job.progress == null ? "Progress not reported" : `${Math.round(job.progress)}%`}
                      </p>
                    </div>
                  )
                })
              )}
              <Link
                href={APP_ROUTES.training}
                className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]"
              >
                Open full run history
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          ) : null}
        </div>
      </div>

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
