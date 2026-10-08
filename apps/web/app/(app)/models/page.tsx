"use client"

import { Suspense, useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import {
  BuiltInModelsPanel,
  trainableBuiltInSuggestions,
  useBuiltInModelItems,
} from "@/components/intelligence/built-in-models-panel"
import { useModelsData } from "@/components/intelligence/models/use-models-data"
import { PAGE_FRAME, TYPE } from "@/lib/design-system"
import { TrainingWorkbench } from "@/components/training/training-workbench"
import { ModelsStage } from "@/components/intelligence/pages/models-stage"
import { studioIntentById } from "@/lib/intelligence/model-catalog-display"
import { APP_ROUTES } from "@/lib/app-routes"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { connectorsApi, mlModelsApi } from "@/lib/api"
import { connectorVendorKey } from "@/lib/connectors"
import { mlProviderVendorKey } from "@/lib/brand-vendor"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { useAuth } from "@/lib/auth-context"
import type { MlModelType } from "@/types/api"
import {
  MODEL_TYPE_CATALOG,
  TASK_TYPE_SUGGESTIONS,
  applyRegistryTemplate,
  connectedDataSources,
  defaultBaseModelForType,
  modelTypeMeta,
  preferredBaseModelForType,
  resolveBaseModelOptions,
  stackLayerById,
  templateForLayer,
  type MlStackLayerId,
} from "@/lib/ml-registry-catalog"
import { ChevronDown, RefreshCw, Layers3 } from "lucide-react"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"

const MORE_ANCHORS = ["built-in", "training", "fine-tunes"]

function formatType(value: string): string {
  return value.replace(/_/g, " ")
}

export default function ModelsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user } = useAuth()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [modelType, setModelType] = useState<MlModelType>("fine_tuned_llm")
  const [baseModel, setBaseModel] = useState("")
  const [taskType, setTaskType] = useState("")
  // Model Studio intent (?intent=...) — its task profile and preferred base
  // win over the per-type defaults so e.g. "Predict outcome" and "Classify"
  // register different models.
  const [intentPreset, setIntentPreset] = useState<{
    modelType: MlModelType
    taskType: string
    preferredBaseModel: string
  } | null>(null)
  const linkedToBuiltIn = searchParams.get("tab") === "built-in"
  const moreRef = useRef<HTMLDetailsElement>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  // Links into the bottom disclosure (?tab=built-in, #built-in, #training, #fine-tunes) open it and scroll there.
  useEffect(() => {
    function openFor(target: string | null) {
      if (!target) return
      setMoreOpen(true)
      window.requestAnimationFrame(() => document.getElementById(target)?.scrollIntoView({ block: "start" }))
    }
    const fromHash = () => {
      const hash = window.location.hash.slice(1)
      openFor(MORE_ANCHORS.includes(hash) ? hash : null)
    }
    openFor(linkedToBuiltIn ? "built-in" : null)
    fromHash()
    window.addEventListener("hashchange", fromHash)
    return () => window.removeEventListener("hashchange", fromHash)
  }, [linkedToBuiltIn])
  const [selectedTemplateLayer, setSelectedTemplateLayer] = useState<MlStackLayerId | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  const modelsData = useModelsData(Boolean(user))
  const { models, error, isLoading, isValidating, refresh, mutateList: mutate } = modelsData
  const builtIn = useBuiltInModelItems()
  const builtInSuggestions = useMemo(() => trainableBuiltInSuggestions(builtIn.items), [builtIn.items])

  const { data: connectorData } = useSWR(user ? "connectors-for-ml" : null, () =>
    connectorsApi.list()
  )

  const connectedVendorKeys = useMemo(() => {
    const keys = new Set<string>()
    const connectedStatuses = new Set(["connected", "healthy", "active", "syncing"])
    for (const row of connectorData?.connectors ?? []) {
      const status = String(row.status ?? "").toLowerCase()
      if (connectedStatuses.has(status)) {
        keys.add(connectorVendorKey(row.type ?? row.vendor ?? ""))
      }
    }
    return keys
  }, [connectorData])

  const dataSources = useMemo(() => connectedDataSources(connectedVendorKeys), [connectedVendorKeys])

  const baseModelOptions = useMemo(
    () => resolveBaseModelOptions(modelType, connectedVendorKeys),
    [modelType, connectedVendorKeys]
  )

  useEffect(() => {
    if (!createOpen || selectedTemplateLayer) return
    if (intentPreset && intentPreset.modelType === modelType) {
      setBaseModel(preferredBaseModelForType(modelType, intentPreset.preferredBaseModel, connectedVendorKeys))
      setTaskType(intentPreset.taskType)
      return
    }
    const next = defaultBaseModelForType(modelType, connectedVendorKeys)
    setBaseModel(next)
    setTaskType(TASK_TYPE_SUGGESTIONS[modelType][0] ?? "")
  }, [modelType, connectedVendorKeys, createOpen, selectedTemplateLayer, intentPreset])

  function resetRegisterForm() {
    setName("")
    setDescription("")
    setModelType("fine_tuned_llm")
    setTaskType(TASK_TYPE_SUGGESTIONS.fine_tuned_llm[0] ?? "")
    setBaseModel(defaultBaseModelForType("fine_tuned_llm", connectedVendorKeys))
  }

  function openRegisterDialog() {
    setSelectedTemplateLayer(null)
    setIntentPreset(null)
    resetRegisterForm()
    setCreateOpen(true)
  }

  useEffect(() => {
    if (searchParams.get("action") !== "register") return
    const intent = studioIntentById(searchParams.get("intent"))
    openRegisterDialog()
    if (intent) {
      setIntentPreset({
        modelType: intent.modelType,
        taskType: intent.taskType,
        preferredBaseModel: intent.preferredBaseModel,
      })
      setModelType(intent.modelType)
    }
  }, [searchParams])

  function clearTemplateSelection() {
    setSelectedTemplateLayer(null)
  }

  function applyLayerTemplate(layerId: MlStackLayerId) {
    const preset = applyRegistryTemplate(templateForLayer(layerId), connectedVendorKeys)
    setSelectedTemplateLayer(layerId)
    setModelType(preset.modelType)
    setName(preset.name)
    setDescription(preset.description)
    setTaskType(preset.taskType)
    setBaseModel(preset.baseModel)
    setCreateOpen(true)
    toast.message("Template applied", {
      description: "Customize name, base model, and task profile before creating.",
    })
  }

  async function handleCreate() {
    if (!name.trim()) {
      toast.error("Model name is required")
      return
    }
    const selectedBase = baseModelOptions.find((o) => o.id === baseModel)
    if (selectedBase?.availability === "requires_connection") {
      toast.error("Connect a data source first", {
        description: `This base model needs a ${selectedBase.connectorVendor ?? "data"} connector.`,
      })
      return
    }
    setIsCreating(true)
    try {
      const created = await mlModelsApi.create({
        name: name.trim(),
        model_type: modelType,
        description: description.trim() || undefined,
        base_model: baseModel.trim() || undefined,
        task_type: taskType.trim() || undefined,
      })
      toast.success("Model registered")
      setCreateOpen(false)
      setSelectedTemplateLayer(null)
      setName("")
      setDescription("")
      setBaseModel("")
      setTaskType("")
      await mutate()
      router.push(`/models/${created.id}`)
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to create model"
      toast.error(message.includes("Upgrade required") ? "Upgrade to Control or Command to register models" : message)
    } finally {
      setIsCreating(false)
    }
  }

  const selectedTypeMeta = modelTypeMeta(modelType)
  const selectedBaseOption = baseModelOptions.find((o) => o.id === baseModel)
  const activeTemplateLayer = selectedTemplateLayer ? stackLayerById(selectedTemplateLayer) : undefined
  const groupedBaseModels = useMemo(() => {
    const groups = new Map<string, typeof baseModelOptions>()
    for (const option of baseModelOptions) {
      const list = groups.get(option.provider) ?? []
      list.push(option)
      groups.set(option.provider, list)
    }
    return [...groups.entries()]
  }, [baseModelOptions])

  return (
    <AppShell title={SURFACE_COPY.models.title}>
      <div className={PAGE_FRAME} data-composition="understand">
        <GravitrePageHeader
          eyebrow="Build / Models"
          titleScale="display"
          title={SURFACE_COPY.models.title}
          description={SURFACE_COPY.models.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <AskGravitreSummonButton
                className="text-[13px]"
                prompt="Look at our models: which ones are in production, which need attention, and what should we improve or retrain next? Use only real registry evidence."
              />
              <Button variant="outline" onClick={() => void refresh()} disabled={isValidating}>
                <RefreshCw className={cn("h-4 w-4", isValidating && "animate-spin")} aria-hidden />
                Refresh
              </Button>
              <Button asChild>
                <Link href={APP_ROUTES.intelligenceModelStudio}>New model</Link>
              </Button>
            </div>
          }
        />

        <IntelligenceShell activeTab="models" loadState={isLoading && models.length === 0 ? "LOADING" : "READY"}>
          <div className="space-y-6 pt-2">
            <section aria-labelledby="models-yours-heading" className="space-y-6">
              <h2 id="models-yours-heading" className="sr-only">
                Your models
              </h2>
              {error ? (
                <WorkSectionErrorCard
                  title="Could not load models"
                  message={error instanceof Error ? error.message : "Unknown error"}
                  error={error}
                  onRetry={() => void refresh()}
                />
              ) : (
                <ModelsStage
                  data={modelsData}
                  builtInSuggestions={builtInSuggestions}
                  onRegister={() => router.push(APP_ROUTES.intelligenceModelStudio)}
                />
              )}
            </section>

            {/*
              Not in the v2 design's main flow, but other pages link here
              (?tab=built-in, #built-in, #training, #fine-tunes), so they live in
              one disclosure at the bottom that opens when a link targets it.
            */}
            <details
              ref={moreRef}
              open={moreOpen}
              onToggle={(e) => setMoreOpen((e.currentTarget as HTMLDetailsElement).open)}
              className="group rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]"
            >
              <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-5 py-3 [&::-webkit-details-marker]:hidden">
                <span className="flex flex-col">
                  <span className="text-sm font-medium text-[color:var(--g-text-primary)]">
                    Built-in models, training runs and fine-tunes
                  </span>
                  <span className={TYPE.meta}>Models Gravitre provides, and the fine-tuning jobs behind your own.</span>
                </span>
                <ChevronDown
                  className="h-4 w-4 shrink-0 text-[color:var(--g-text-muted)] transition-transform group-open:rotate-180"
                  aria-hidden
                />
              </summary>
              {moreOpen ? (
                <div className="space-y-10 border-t border-[color:var(--g-border-subtle)] px-5 py-6">
                  <section id="built-in" aria-labelledby="models-built-in-heading" className="scroll-mt-24 space-y-4">
                    <div>
                      <h2 id="models-built-in-heading" className={TYPE.cardTitle}>
                        Built-in models
                      </h2>
                      <p className={cn(TYPE.bodyMuted, "mt-0.5")}>
                        Models Gravitre provides and trains on your organization&apos;s data.
                      </p>
                    </div>
                    <BuiltInModelsPanel />
                  </section>

                  <section id="training" aria-labelledby="models-training-heading" className="scroll-mt-24 space-y-4">
                    <div>
                      <h2 id="models-training-heading" className={TYPE.cardTitle}>
                        Training runs
                      </h2>
                      <p className={cn(TYPE.bodyMuted, "mt-0.5")}>
                        Fine-tuning jobs and their progress. Datasets for them live in Intelligence › Data.
                      </p>
                    </div>
                    <Suspense fallback={<p className={TYPE.bodyMuted}>Loading training runs…</p>}>
                      <TrainingWorkbench embedded section="jobs" />
                    </Suspense>
                  </section>

                  <section id="fine-tunes" aria-labelledby="models-fine-tunes-heading" className="scroll-mt-24 space-y-4">
                    <div>
                      <h2 id="models-fine-tunes-heading" className={TYPE.cardTitle}>
                        Fine-tuned models
                      </h2>
                      <p className={cn(TYPE.bodyMuted, "mt-0.5")}>Finished fine-tunes and which agents use them.</p>
                    </div>
                    <Suspense fallback={<p className={TYPE.bodyMuted}>Loading fine-tuned models…</p>}>
                      <TrainingWorkbench embedded section="models" />
                    </Suspense>
                  </section>
                </div>
              ) : null}
            </details>
          </div>
        </IntelligenceShell>
      </div>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open)
          if (!open) {
            setSelectedTemplateLayer(null)
            resetRegisterForm()
          }
        }}
      >
        <DialogContent className="flex max-h-[min(92vh,760px)] flex-col gap-0 overflow-hidden p-0 sm:max-w-xl">
          <DialogHeader className="shrink-0 space-y-3 border-b border-border/60 px-6 pb-4 pt-6">
            <DialogTitle className="flex items-center gap-2 pr-8">
              <Layers3 className="h-4 w-4 text-[color:var(--g-emerald-deep)]" />
              Register model
            </DialogTitle>
            <DialogDescription className="text-left">
              Creates a draft model. Train, evaluate, and inspect runs in{" "}
              <Link href={APP_ROUTES.intelligenceModelStudio} className="text-primary underline-offset-4 hover:underline">
                Model Studio
              </Link>
              , then deploy from the model page.
            </DialogDescription>
            {activeTemplateLayer ? (
              <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2.5 text-left text-xs">
                <p className="font-semibold text-success">
                  Template: {activeTemplateLayer.title}
                </p>
                <p className="mt-1 leading-relaxed text-foreground/80">
                  Pre-filled for this type. Adjust name, base model, or task before creating.
                </p>
              </div>
            ) : null}
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4">
            <div className="space-y-2">
              <Label htmlFor="model-name">Name</Label>
              <Input
                id="model-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Lead scoring classifier"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-type">Model type</Label>
              <Select
                value={modelType}
                onValueChange={(v) => {
                  clearTemplateSelection()
                  setModelType(v as MlModelType)
                }}
              >
                <SelectTrigger id="model-type" className="h-auto min-h-10 py-2">
                  <SelectValue>
                    {selectedTypeMeta
                      ? `${selectedTypeMeta.label}: ${selectedTypeMeta.tagline}`
                      : "Select model type"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {MODEL_TYPE_CATALOG.map((t) => (
                    <SelectItem key={t.value} value={t.value} textValue={t.label}>
                      <span className="font-medium">{t.label}</span>
                      <span className="ml-2 text-muted-foreground">{t.tagline}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedTypeMeta ? (
                <p className="text-xs text-muted-foreground">
                  Examples: {selectedTypeMeta.examples.join(", ")}
                </p>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="base-model">Base model</Label>
              <Select
                value={baseModel}
                onValueChange={(v) => {
                  clearTemplateSelection()
                  setBaseModel(v)
                }}
              >
                <SelectTrigger id="base-model" className="h-auto min-h-10 py-2">
                  <SelectValue placeholder="Select base model">
                    {selectedBaseOption ? (
                      <span className="flex items-center gap-2 text-left">
                        <ConnectorIcon
                          vendor={mlProviderVendorKey(selectedBaseOption.provider)}
                          size="xs"
                          showStatusIndicator={false}
                          className="shrink-0"
                        />
                        <span className="flex flex-col items-start gap-0.5">
                          <span>
                            {selectedBaseOption.label} · {selectedBaseOption.provider}
                          </span>
                          <span className="font-mono text-[10px] text-muted-foreground">
                            {selectedBaseOption.id}
                          </span>
                        </span>
                      </span>
                    ) : (
                      "Select base model"
                    )}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent className="max-h-80">
                  {groupedBaseModels.map(([provider, options]) => (
                    <SelectGroup key={provider}>
                      <SelectLabel className="flex items-center gap-2">
                        <ConnectorIcon
                          vendor={mlProviderVendorKey(provider)}
                          size="xs"
                          showStatusIndicator={false}
                        />
                        {provider}
                      </SelectLabel>
                      {options.map((option) => (
                        <SelectItem
                          key={option.id}
                          value={option.id}
                          textValue={`${option.label} ${option.provider} ${option.id}`}
                          disabled={option.availability === "requires_connection"}
                          className="items-start py-2"
                        >
                          <div className="flex items-start gap-2">
                            <ConnectorIcon
                              vendor={mlProviderVendorKey(option.provider)}
                              size="xs"
                              showStatusIndicator={false}
                              className="mt-0.5 shrink-0"
                            />
                            <div className="flex flex-col gap-1">
                            <span className="flex flex-wrap items-center gap-1.5">
                              <span className="font-medium">{option.label}</span>
                              {option.versionTag ? (
                                <span className="font-mono text-[10px] text-muted-foreground">
                                  {option.versionTag}
                                </span>
                              ) : null}
                              {option.recommended ? (
                                <Badge variant="outline" className="h-4 px-1 text-[9px]">
                                  Recommended
                                </Badge>
                              ) : null}
                              {option.fineTunable ? (
                                <Badge
                                  variant="outline"
                                  className="h-4 border-success/30 px-1 text-[9px] text-success"
                                >
                                  Fine-tunable
                                </Badge>
                              ) : null}
                            </span>
                            <span className="font-mono text-[10px] text-muted-foreground">{option.id}</span>
                            <span className="text-[11px] leading-snug text-muted-foreground">
                              {option.description}
                            </span>
                            </div>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
                </SelectContent>
              </Select>
              {baseModelOptions.some((o) => o.availability === "requires_connection") ? (
                <p className="text-xs text-warning">
                  Platform LLMs (OpenAI, Anthropic, Google, xAI) are always selectable. Warehouse and
                  tabular bases stay in the list but are disabled until you connect the matching
                  source on{" "}
                  <Link href="/connectors" className="underline underline-offset-2">
                    Connectors
                  </Link>
                  .
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  All platform foundation models for this type are listed. Switch model type above to
                  see classifier, forecaster, or anomaly bases.
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="task-type">Task profile (optional)</Label>
              <Select
                value={taskType}
                onValueChange={(v) => {
                  clearTemplateSelection()
                  setTaskType(v)
                }}
              >
                <SelectTrigger id="task-type">
                  <SelectValue placeholder="Select task profile">
                    {taskType ? formatType(taskType) : "Select task profile"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {TASK_TYPE_SUGGESTIONS[modelType].map((t) => (
                    <SelectItem key={t} value={t} textValue={formatType(t)}>
                      {formatType(t)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-desc">Description (optional)</Label>
              <Input
                id="model-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Scores inbound leads for sales routing"
              />
            </div>
          </div>

          <DialogFooter className="shrink-0 border-t border-border/60 bg-background px-6 py-4">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleCreate()} disabled={isCreating || !baseModel}>
              {isCreating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
