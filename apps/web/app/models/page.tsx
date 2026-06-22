"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { PageHeader } from "@/components/gravitre/page-header"
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
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { mlModelsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import type { MlModelSummary, MlModelType } from "@/types/api"
import { Brain, Plus, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

const MODEL_TYPES: { value: MlModelType; label: string }[] = [
  { value: "classifier", label: "Classifier" },
  { value: "fine_tuned_llm", label: "Fine-tuned LLM" },
  { value: "anomaly_detector", label: "Anomaly detector" },
  { value: "forecaster", label: "Forecaster" },
]

const statusStyles: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  training: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  validating: "bg-violet-500/10 text-violet-400 border-violet-500/20",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  archived: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
}

function formatType(value: string): string {
  return value.replace(/_/g, " ")
}

function ModelRow({ model }: { model: MlModelSummary }) {
  const status = model.status ?? "draft"
  return (
    <Link
      href={`/models/${model.id}`}
      className="block rounded-xl border border-border/60 bg-card/40 p-4 transition-colors hover:border-blue-500/30 hover:bg-card/70"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground line-clamp-2">{model.name}</p>
          {model.description ? (
            <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{model.description}</p>
          ) : null}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="capitalize">{formatType(model.modelType)}</span>
            <span>v{model.currentVersion}</span>
            {model.deployedVersion != null ? (
              <span className="text-emerald-400">deployed v{model.deployedVersion}</span>
            ) : null}
          </div>
        </div>
        <Badge variant="outline" className={cn("shrink-0 capitalize", statusStyles[status] ?? statusStyles.draft)}>
          {status}
        </Badge>
      </div>
    </Link>
  )
}

export default function ModelsPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [createOpen, setCreateOpen] = useState(false)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [modelType, setModelType] = useState<MlModelType>("classifier")
  const [baseModel, setBaseModel] = useState("")
  const [isCreating, setIsCreating] = useState(false)

  const { data, error, isLoading, mutate, isValidating } = useSWR(
    user ? "ml-models-list" : null,
    () => mlModelsApi.list()
  )

  const models = data?.models ?? []

  async function handleCreate() {
    if (!name.trim()) {
      toast.error("Model name is required")
      return
    }
    setIsCreating(true)
    try {
      const created = await mlModelsApi.create({
        name: name.trim(),
        model_type: modelType,
        description: description.trim() || undefined,
        base_model: baseModel.trim() || undefined,
      })
      toast.success("Model registered")
      setCreateOpen(false)
      setName("")
      setDescription("")
      setBaseModel("")
      await mutate()
      router.push(`/models/${created.id}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create model")
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <AppShell title="Model Registry">
      <div className="mx-auto max-w-4xl p-4 sm:p-6 space-y-6">
        <PageHeader
          title="Model Registry"
          description="Register, version, and deploy org-scoped ML models used by workflows and agents."
          icon={Brain}
          actions={
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("h-4 w-4 mr-1", isValidating && "animate-spin")} />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Register model
              </Button>
            </div>
          }
        />

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
          <EmptyState
            icon={Brain}
            title="No models yet"
            description="Register a classifier, forecaster, or fine-tuned model to track versions and deployment."
            action={{ label: "Register model", onClick: () => setCreateOpen(true) }}
          />
        ) : (
          <div className="space-y-3">
            {models.map((model) => (
              <ModelRow key={model.id} model={model} />
            ))}
          </div>
        )}

        <p className="text-xs text-muted-foreground">
          Training datasets and jobs live on{" "}
          <Link href="/training" className="text-primary underline-offset-4 hover:underline">
            Training
          </Link>
          . Link a dataset when registering models that need fine-tuning data.
        </p>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Register model</DialogTitle>
            <DialogDescription>
              Creates a draft entry in the org model registry. Train and deploy versions from the detail page.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
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
              <Label htmlFor="model-type">Type</Label>
              <Select value={modelType} onValueChange={(v) => setModelType(v as MlModelType)}>
                <SelectTrigger id="model-type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
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
            {modelType === "fine_tuned_llm" ? (
              <div className="space-y-2">
                <Label htmlFor="base-model">Base model (optional)</Label>
                <Input
                  id="base-model"
                  value={baseModel}
                  onChange={(e) => setBaseModel(e.target.value)}
                  placeholder="gpt-4.1-mini"
                />
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => void handleCreate()} disabled={isCreating}>
              {isCreating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
