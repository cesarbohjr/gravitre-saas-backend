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
import { ImproveAgentPanel } from "@/components/intelligence/pages/improve-agent-panel"
import { ExternalDatasetsSection } from "@/components/intelligence/external-datasets-section"
import { SelectionInspector } from "@/components/gravitre/selection-inspector"
import { useIsMobile } from "@/hooks/use-mobile"
import { Button } from "@/components/ui/button"
import { mlModelsApi, trainingApi } from "@/lib/api"
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
  const [improvePending, setImprovePending] = useState(false)
  const improvingAgent = intent === "improve_agent"
  const [datasetSaving, setDatasetSaving] = useState(false)

  const { data: modelsData, isLoading: modelsLoading, error: modelsError, mutate: mutateModels } = useSWR(
    enabled &&
      (segment === "evaluate" ||
        segment === "deploy")
      ? "ml-models-list-studio"
      : null,
    () => mlModelsApi.list(),
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
  const models = useMemo(() => modelsData?.models ?? [], [modelsData])
  const catalog = useMemo(() => models.map(formatModelCatalogRow), [models])
  const evaluateModels = catalog.filter((m) =>
    ["ready", "validating", "evaluating", "training"].includes(m.technicalStatus),
  )
  const deployModels = catalog.filter(
    (m) => m.technicalStatus === "ready" || m.technicalStatus === "deployed",
  )
  const jobs = jobsData?.jobs ?? []
  const datasets = datasetsData?.datasets ?? []
  function startCreate() {
    const params = new URLSearchParams({ action: "register" })
    if (intent) params.set("intent", intent)
    router.push(`${APP_ROUTES.models}?${params.toString()}`)
  }

  return (
    <div className="space-y-6">
      {((segment === "evaluate" || segment === "deploy") && modelsError) || jobsError || datasetsError ? (
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
                  onClick={() => { setSegment(item.id); setInspectorOpen(false); }}
                  disabled={datasetSaving || improvePending}
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
                          disabled={improvePending}
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
                    pending={improvePending}
                    title={STUDIO_INTENTS.find((item) => item.id === intent)?.label ?? "Model intent"}
                    description={improvingAgent ? "Pick an agent and choose what to change." : "Review the model's purpose before registering it."}
                    className="flex-1 border-l border-divide p-4"
                  >
                    {improvingAgent ? (
                      <ImproveAgentPanel enabled={enabled} onPendingChange={setImprovePending} />
                    ) : (
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
                    )}
                  </SelectionInspector>
                ) : (
                  <p className="sr-only">Select an intent — inspector stays closed until then.</p>
                )}
              </div>
              {improvingAgent && !compactInspector ? null : (
                <Button
                  onClick={() => compactInspector ? setInspectorOpen(true) : startCreate()}
                  disabled={!intent}
                  className="min-h-11 gap-1.5"
                >
                  {improvingAgent ? "Choose agent" : compactInspector ? "Review selected intent" : "Continue to register"}
                  <ArrowRight className="h-4 w-4" aria-hidden />
                </Button>
              )}
            </div>
          ) : null}

          {segment === "train" ? (
            <div className="space-y-4">
              <ExternalDatasetsSection enabled={enabled} source="model_studio" onSavingChange={setDatasetSaving} />
              {datasetsError && datasets.length === 0 ? null : datasetsLoading ? (
                <p className="text-sm text-muted-foreground">Loading datasets…</p>
              ) : datasets.length === 0 ? (
                <EmptyState
                  title="Upload your own training data"
                  description="Create or upload a private dataset for training. Free public datasets from Hugging Face and Kaggle can be added above."
                  action={{
                    label: "Create or upload dataset",
                    onClick: () => {
                      router.push(APP_ROUTES.intelligenceData)
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
                href={APP_ROUTES.intelligenceData}
                className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]"
              >
                Manage your datasets in Data
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
                  description="Reported training jobs appear here. Open a run to inspect progress and preparation requirements."
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
                href={`${APP_ROUTES.models}#training`}
                className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]"
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
