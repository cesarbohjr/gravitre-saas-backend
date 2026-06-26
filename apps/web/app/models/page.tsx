"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { ModelRegistryOverview } from "@/components/gravitre/model-registry-overview"
import { EmptyState } from "@/components/gravitre/empty-state"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
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
import type { MlModelSummary, MlModelType } from "@/types/api"
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
  Brain,
  ChevronRight,
  Filter,
  Link2,
  Plus,
  RefreshCw,
  Sparkles,
} from "lucide-react"
import { cn } from "@/lib/utils"

const statusStyles: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  training: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  validating: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  archived: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
}

const availabilityBadge: Record<string, string> = {
  platform: "bg-violet-500/10 text-violet-300 border-violet-500/25",
  connected: "bg-emerald-500/10 text-emerald-400 border-emerald-500/25",
  requires_connection: "bg-amber-500/10 text-amber-400 border-amber-500/25",
}

function formatType(value: string): string {
  return value.replace(/_/g, " ")
}

function ModelRow({ model, index }: { model: MlModelSummary; index: number }) {
  const status = model.status ?? "draft"
  const meta = modelTypeMeta(model.modelType)
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
    >
      <Link
        href={`/models/${model.id}`}
        className="group block rounded-xl border border-border/60 bg-card/40 p-4 transition-all hover:border-violet-500/30 hover:bg-card/70 hover:shadow-sm"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium text-foreground line-clamp-1">{model.name}</p>
              {meta ? (
                <span className="rounded-md bg-secondary/80 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {meta.label}
                </span>
              ) : null}
            </div>
            {model.description ? (
              <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{model.description}</p>
            ) : null}
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span className="capitalize">{formatType(model.modelType)}</span>
              {model.baseModel ? <span className="truncate">base: {model.baseModel}</span> : null}
              <span>v{model.currentVersion}</span>
              {model.deployedVersion != null ? (
                <span className="text-emerald-400">live v{model.deployedVersion}</span>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <Badge variant="outline" className={cn("capitalize", statusStyles[status] ?? statusStyles.draft)}>
              {status}
            </Badge>
            <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </div>
        </div>
      </Link>
    </motion.div>
  )
}

export default function ModelsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [modelType, setModelType] = useState<MlModelType>("fine_tuned_llm")
  const [baseModel, setBaseModel] = useState("")
  const [taskType, setTaskType] = useState("")
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [typeFilter, setTypeFilter] = useState<string>("all")
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
      toast.error(err instanceof Error ? err.message : "Failed to create model")
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
    <AppShell title="Model Registry">
      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        <PageHeader
          title="Model Registry"
          description="Register, version, and deploy org-scoped ML models used by workflows and agents."
          icon={Brain}
          iconColor="from-violet-500/20 to-fuchsia-500/20 ring-violet-500/20"
          actions={
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("mr-1 h-4 w-4", isValidating && "animate-spin")} />
                Refresh
              </Button>
              <Button size="sm" onClick={openRegisterDialog}>
                <Plus className="mr-1 h-4 w-4" />
                Register model
              </Button>
            </div>
          }
        />

        <ModelRegistryOverview
          totalModels={models.length}
          deployedCount={stats.deployed}
          trainingCount={stats.training}
          connectedDataSources={dataSources}
          selectedLayer={selectedTemplateLayer}
          onSelectTemplate={applyLayerTemplate}
        />

        {models.length > 0 ? (
          <StatsGrid columns={4}>
            <StatCard label="Registered" value={models.length} variant="info" />
            <StatCard label="Deployed" value={stats.deployed} variant="success" />
            <StatCard label="Ready" value={stats.ready} variant="default" />
            <StatCard label="In training" value={stats.training} variant="warning" />
          </StatsGrid>
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

        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        ) : error ? (
          <WorkSectionErrorCard
            title="Could not load models"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={() => mutate()}
          />
        ) : models.length === 0 ? (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }}>
            <EmptyState
              icon={Brain}
              title="No models yet"
              description="Register a classifier, forecaster, fine-tuned LLM, or anomaly detector. Base models adapt to your connected data sources and platform LLM providers."
              action={{ label: "Register model", onClick: openRegisterDialog }}
            />
          </motion.div>
        ) : filteredModels.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 bg-secondary/20 p-8 text-center text-sm text-muted-foreground">
            No models match the current filters.
          </div>
        ) : (
          <div className="space-y-3">
            <AnimatePresence mode="popLayout">
              {filteredModels.map((model, index) => (
                <ModelRow key={model.id} model={model} index={index} />
              ))}
            </AnimatePresence>
          </div>
        )}

        <div className="rounded-xl border border-border/50 bg-secondary/20 p-4 text-xs text-muted-foreground">
          <p className="font-medium text-foreground/90">How it fits together</p>
          <ol className="mt-2 list-decimal space-y-1 pl-4">
            <li>
              Register a model here with type + base algorithm or foundation LLM.
            </li>
            <li>
              Attach training data on{" "}
              <Link href="/training" className="text-primary underline-offset-4 hover:underline">
                Training
              </Link>{" "}
              and start a job linked to this registry entry.
            </li>
            <li>Deploy a version, then reference the model from workflows, agents, or Meson nodes.</li>
          </ol>
          {dataSources.length === 0 ? (
            <p className="mt-3 flex flex-wrap items-center gap-1">
              <Link2 className="h-3.5 w-3.5" />
              Connect PostgreSQL, Snowflake, or Segment on{" "}
              <Link href="/connectors" className="text-primary underline-offset-4 hover:underline">
                Connectors
              </Link>{" "}
              to unlock tabular base models.
            </p>
          ) : null}
        </div>
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
              <Sparkles className="h-4 w-4 text-violet-400" />
              Register model
            </DialogTitle>
            <DialogDescription className="text-left">
              Creates a draft registry entry. Train on{" "}
              <Link href="/training" className="text-primary underline-offset-4 hover:underline">
                Training
              </Link>
              , then deploy from the model detail page.
            </DialogDescription>
            {activeTemplateLayer ? (
              <div className="rounded-lg border border-violet-300/80 bg-violet-50 px-3 py-2.5 text-left text-xs dark:border-violet-500/30 dark:bg-violet-950/50">
                <p className="font-semibold text-violet-950 dark:text-violet-100">
                  Template: {activeTemplateLayer.title}
                </p>
                <p className="mt-1 leading-relaxed text-violet-800 dark:text-violet-200">
                  Pre-filled for this stack layer — adjust name, base model, or task profile before creating.
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
                      ? `${selectedTypeMeta.label} — ${selectedTypeMeta.tagline}`
                      : "Select model type"}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {MODEL_TYPE_CATALOG.map((t) => (
                    <SelectItem key={t.value} value={t.value} textValue={t.label}>
                      <span className="font-medium">{t.label}</span>
                      <span className="ml-2 text-muted-foreground">— {t.tagline}</span>
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
                                  className="h-4 border-emerald-500/30 px-1 text-[9px] text-emerald-400"
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
                <p className="text-xs text-amber-600 dark:text-amber-400/90">
                  Some bases need a data connector.{" "}
                  <Link href="/connectors" className="underline underline-offset-2">
                    Connect data sources
                  </Link>
                </p>
              ) : null}
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
