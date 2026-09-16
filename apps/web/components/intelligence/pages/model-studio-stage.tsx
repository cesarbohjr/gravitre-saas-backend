"use client"

/**
 * I8 — Model Studio: Create · Train · Evaluate · Deploy · Runs with intent-first create.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { EmptyState } from "@/components/gravitre/empty-state"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { IntelligenceAskCommandSurface } from "@/components/intelligence/shell"
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
  const [intent, setIntent] = useState<StudioIntentId | null>(null)

  const { data: modelsData, isLoading: modelsLoading } = useSWR(
    enabled && (segment === "evaluate" || segment === "deploy") ? "ml-models-list-studio" : null,
    () => mlModelsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: jobsData, isLoading: jobsLoading } = useSWR(
    enabled && (segment === "train" || segment === "runs") ? "training-jobs-studio" : null,
    () => trainingApi.listJobs(),
    { revalidateOnFocus: false },
  )
  const { data: datasetsData, isLoading: datasetsLoading } = useSWR(
    enabled && segment === "train" ? "training-datasets-studio" : null,
    () => trainingApi.listDatasets(),
    { revalidateOnFocus: false },
  )

  const models = modelsData?.models ?? []
  const catalog = useMemo(() => models.map(formatModelCatalogRow), [models])
  const evaluateModels = catalog.filter((m) =>
    ["ready", "validating", "evaluating", "training"].includes(m.technicalStatus),
  )
  const deployModels = catalog.filter((m) => m.technicalStatus === "ready" || m.technicalStatus === "deployed")
  const jobs = jobsData?.jobs ?? []
  const datasets = datasetsData?.datasets ?? []

  function startCreate() {
    const params = new URLSearchParams({ action: "register" })
    if (intent) params.set("intent", intent)
    router.push(`${APP_ROUTES.models}?${params.toString()}`)
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div>
          <p className={TYPE.eyebrow}>Workspace</p>
          <p className={cn(TYPE.meta, "mt-0.5")}>
            Intent first, then training. Train and Runs use the existing training system — not a
            separate hub tab.
          </p>
        </div>
        <SegmentedControl
          ariaLabel="Model Studio action"
          options={[...STUDIO_SEGMENTS]}
          value={segment}
          onChange={setSegment}
          className="w-full max-w-full flex-wrap"
        />
      </div>

      {segment === "create" ? (
        <div className="space-y-4">
          <p className="text-sm text-foreground">What do you want this model to do?</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {STUDIO_INTENTS.map((item) => {
              const selected = intent === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setIntent(item.id)}
                  aria-pressed={selected}
                  className={cn(
                    "rounded-[var(--np-radius-md)] border px-4 py-3 text-left transition-colors",
                    selected
                      ? "border-[color:var(--g-brand-border)] bg-[color:var(--g-intelligence-surface)]"
                      : "border-divide hover:border-[color:var(--g-brand-border)]",
                  )}
                >
                  <p className="text-sm font-medium text-foreground">{item.label}</p>
                  <p className={cn(TYPE.meta, "mt-1")}>{item.description}</p>
                </button>
              )
            })}
          </div>
          <Button onClick={startCreate} disabled={!intent} className="gap-1.5">
            Continue to register
            <ArrowRight className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      ) : null}

      {segment === "train" ? (
        <div className="space-y-4">
          {datasetsLoading ? (
            <p className="text-sm text-muted-foreground">Loading datasets…</p>
          ) : datasets.length === 0 ? (
            <EmptyState
              title="No training datasets yet"
              description="Datasets and jobs still live on the Training route. Model Studio opens that workspace here."
              action={{
                label: "Open training workspace",
                onClick: () => {
                  window.location.href = APP_ROUTES.training
                },
              }}
            />
          ) : (
            <ul className="space-y-2">
              {datasets.slice(0, 8).map((dataset) => (
                <li
                  key={dataset.id}
                  className="rounded-[var(--np-radius-md)] border border-divide px-3 py-2 text-sm"
                >
                  {dataset.name}
                </li>
              ))}
            </ul>
          )}
          <Link
            href={APP_ROUTES.training}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand)] hover:underline"
          >
            Open full training workspace
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : null}

      {segment === "evaluate" ? (
        <div className="space-y-3">
          {modelsLoading ? (
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
                className="block rounded-[var(--np-radius-md)] border border-divide px-3 py-2 hover:border-[color:var(--g-brand-border)]"
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
          {modelsLoading ? (
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
                className="block rounded-[var(--np-radius-md)] border border-divide px-3 py-2 hover:border-[color:var(--g-brand-border)]"
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
          {jobsLoading ? (
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
                <div key={job.id} className="rounded-[var(--np-radius-md)] border border-divide px-3 py-2">
                  <p className="text-sm font-medium">{job.dataset_name || job.model_base}</p>
                  <p className={TYPE.meta}>
                    {status.phrase} · {Math.round(job.progress ?? 0)}%
                  </p>
                </div>
              )
            })
          )}
          <Link
            href={APP_ROUTES.training}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-[color:var(--g-brand)] hover:underline"
          >
            Open full run history
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      ) : null}

      <IntelligenceAskCommandSurface enabled={enabled} pageSuggestedQuestions={suggestedQuestions} />
    </div>
  )
}
