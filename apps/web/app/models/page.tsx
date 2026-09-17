"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { BuiltInModelsPanel } from "@/app/intelligence/models/page"
import { Tabs, TabsContent } from "@/components/ui/tabs"
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
  resolveBaseModelOptions,
  stackLayerById,
  templateForLayer,
  type MlStackLayerId,
} from "@/lib/ml-registry-catalog"
import {
  Filter,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { describeStatus } from "@/lib/intelligence/status-language"

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
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [typeFilter, setTypeFilter] = useState<string>("all")
  const [modelsTab, setModelsTab] = useState<"registry" | "built-in">(
    searchParams.get("tab") === "built-in" ? "built-in" : "registry",
  )
  const [selectedTemplateLayer, setSelectedTemplateLayer] = useState<MlStackLayerId | null>(null)
  const [isCreating, setIsCreating] = useState(false)

  const { data, error, isLoading, mutate, isValidating } = useSWR(
    user ? "ml-models-list" : null,
    () => mlModelsApi.list()
  )

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

  const models = data?.models ?? []

  const stats = useMemo(() => {
    const deployed = models.filter((m) => m.status === "deployed" || m.deployedVersion != null).length
    const training = models.filter((m) => m.status === "training" || m.status === "validating").length
    const ready = models.filter((m) => m.status === "ready").length
    return { deployed, training, ready }
  }, [models])

  const filteredModels = useMemo(() => {
    return models.filter((m) => {
      if (statusFilter !== "all" && m.status !== statusFilter) return false
      if (typeFilter !== "all" && m.modelType !== typeFilter) return false
      return true
    })
  }, [models, statusFilter, typeFilter])

  useEffect(() => {
    if (!createOpen || selectedTemplateLayer) return
    const next = defaultBaseModelForType(modelType, connectedVendorKeys)
    setBaseModel(next)
    setTaskType(TASK_TYPE_SUGGESTIONS[modelType][0] ?? "")
  }, [modelType, connectedVendorKeys, createOpen, selectedTemplateLayer])

  function resetRegisterForm() {
    setName("")
    setDescription("")
    setModelType("fine_tuned_llm")
    setTaskType(TASK_TYPE_SUGGESTIONS.fine_tuned_llm[0] ?? "")
    setBaseModel(defaultBaseModelForType("fine_tuned_llm", connectedVendorKeys))
  }

  function openRegisterDialog() {
    setSelectedTemplateLayer(null)
    resetRegisterForm()
    setCreateOpen(true)
  }

  useEffect(() => {
    if (searchParams.get("action") !== "register") return
    const intent = studioIntentById(searchParams.get("intent"))
    openRegisterDialog()
    if (intent) {
      setModelType(intent.modelType)
      setTaskType(TASK_TYPE_SUGGESTIONS[intent.modelType][0] ?? "")
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
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <GravitrePageHeader
          title={SURFACE_COPY.models.title}
          description={SURFACE_COPY.models.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <AskGravitreSummonButton />
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("mr-1 h-4 w-4", isValidating && "animate-spin")} />
                Refresh
              </Button>
              <Button size="sm" asChild>
                <Link href={APP_ROUTES.intelligenceModelStudio}>Create in Studio</Link>
              </Button>
            </div>
          }
        />

        <IntelligenceShell activeTab="models" loadState={isLoading && models.length === 0 ? "LOADING" : "READY"}>

        {/*
          Intelligence redesign Phase 1 (2026-09-11): Built-in Models folded
          into Models as a real tab (no strong technical reason to keep them
          separate — see the Phase 0 proposal). /intelligence/models and its
          /models/built-in alias still work unchanged for existing bookmarks;
          this tab renders the exact same BuiltInModelsPanel component.
        */}
        <Tabs value={modelsTab} onValueChange={(value) => setModelsTab(value as "registry" | "built-in")}>
          <nav aria-label="Models catalog" className="mb-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
            {(
              [
                { id: "registry" as const, label: "Registry" },
                { id: "built-in" as const, label: "Built-in models" },
              ]
            ).map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setModelsTab(item.id)}
                className={cn(
                  "text-xs underline-offset-4",
                  modelsTab === item.id
                    ? "text-[color:var(--g-text-primary)] underline"
                    : "text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]",
                )}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <TabsContent value="built-in" className="pt-4">
            <BuiltInModelsPanel />
          </TabsContent>
          <TabsContent value="registry" className="space-y-6 pt-4">

        {models.length > 0 || isLoading ? (
          <details className="text-sm">
            <summary className="cursor-pointer text-xs text-muted-foreground">Totals</summary>
            <section className="mt-3 grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
              <GravitreMetric
                label="Registered"
                value={isLoading && models.length === 0 ? "—" : models.length}
                hint={isLoading && models.length === 0 ? "Loading models…" : "Registry scope"}
              />
              <GravitreMetric
                label="In production use"
                value={isLoading && models.length === 0 ? "—" : stats.deployed}
                hint="Deployed versions only"
              />
              <GravitreMetric
                label="Ready to deploy"
                value={isLoading && models.length === 0 ? "—" : stats.ready}
              />
              <GravitreMetric
                label="Learning from data"
                value={isLoading && models.length === 0 ? "—" : stats.training}
                hint={describeStatus("training").phrase}
              />
            </section>
          </details>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="h-8 w-[160px] bg-secondary/50 text-xs">
              <SelectValue placeholder="Type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {MODEL_TYPE_CATALOG.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-8 w-[140px] bg-secondary/50 text-xs">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All status</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="training">Training</SelectItem>
              <SelectItem value="ready">Ready</SelectItem>
              <SelectItem value="deployed">Deployed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {error ? (
          <WorkSectionErrorCard
            title="Could not load models"
            message={error instanceof Error ? error.message : "Unknown error"}
            error={error}
            onRetry={() => mutate()}
          />
        ) : (
          <ModelsStage
            models={filteredModels}
            isLoading={isLoading}
            enabled={Boolean(user)}
            onRegister={() => router.push(APP_ROUTES.intelligenceModelStudio)}
          />
        )}
          </TabsContent>
        </Tabs>
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
              <Sparkles className="h-4 w-4 text-primary" />
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
