"use client"

import { use, useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { motion } from "framer-motion"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { ModelDetailInsights } from "@/components/gravitre/model-detail-insights"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { connectorsApi, mlModelsApi } from "@/lib/api"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { connectorVendorKey } from "@/lib/connectors"
import { useAuth } from "@/lib/auth-context"
import {
  connectedDataSources,
  inferenceSampleInputs,
  lookupBaseModelOption,
} from "@/lib/ml-registry-catalog"
import { ArrowLeft, Brain, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"

const statusStyles: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400 border-zinc-500/20",
  training: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  validating: "bg-teal-500/10 text-teal-400 border-teal-500/20",
  ready: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  failed: "bg-red-500/10 text-red-400 border-red-500/20",
  archived: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
}

export default function ModelDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const { user } = useAuth()
  const [isDeploying, setIsDeploying] = useState(false)
  const [isPredicting, setIsPredicting] = useState(false)
  const [predictResult, setPredictResult] = useState<string | null>(null)
  const [predictError, setPredictError] = useState<string | null>(null)

  const { data: model, error, isLoading, mutate, isValidating } = useSWR(
    user ? ["ml-model", id] : null,
    () => mlModelsApi.get(id)
  )

  const { data: connectorData } = useSWR(user ? "connectors-for-ml-detail" : null, () =>
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

  const baseModelOption = useMemo(
    () => (model ? lookupBaseModelOption(model.modelType, model.baseModel, connectedVendorKeys) : undefined),
    [model, connectedVendorKeys]
  )

  const [inferenceJson, setInferenceJson] = useState("[]")

  useEffect(() => {
    if (model) {
      setInferenceJson(JSON.stringify(inferenceSampleInputs(model.modelType), null, 2))
    }
  }, [model?.id, model?.modelType])

  const canDeploy =
    model &&
    (model.status === "ready" || model.status === "deployed") &&
    model.currentVersion > 0

  async function handleDeploy() {
    if (!model) return
    setIsDeploying(true)
    try {
      await mlModelsApi.deploy(id, model.currentVersion || undefined)
      toast.success("Deployment updated", {
        description: `Version ${model.currentVersion} is now active.`,
      })
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Deploy failed")
    } finally {
      setIsDeploying(false)
    }
  }

  async function handleRunInference() {
    if (!model) return
    setIsPredicting(true)
    setPredictError(null)
    setPredictResult(null)
    try {
      const inputs = JSON.parse(inferenceJson) as Record<string, unknown>[]
      if (!Array.isArray(inputs)) {
        throw new Error("Payload must be a JSON array of input objects.")
      }
      const result = await mlModelsApi.predict(id, {
        inputs,
        return_probabilities: model.modelType !== "fine_tuned_llm",
      })
      setPredictResult(JSON.stringify(result, null, 2))
      toast.success("Inference completed", {
        description: result.latencyMs ? `${Math.round(result.latencyMs)} ms` : undefined,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Inference failed"
      setPredictError(message)
      toast.error(message)
    } finally {
      setIsPredicting(false)
    }
  }

  function handleResetInferenceSample() {
    if (!model) return
    setInferenceJson(JSON.stringify(inferenceSampleInputs(model.modelType), null, 2))
    setPredictError(null)
    setPredictResult(null)
  }

  return (
    <AppShell title={model?.name ?? "Model"}>
      <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
        <div className="space-y-6">
        <Button variant="ghost" size="sm" className="-ml-2 h-8" asChild>
          <Link href="/models">
            <ArrowLeft className="mr-1 h-4 w-4" />
            {SURFACE_COPY.models.title}
          </Link>
        </Button>

        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-32 w-full rounded-xl" />
            <Skeleton className="h-48 w-full rounded-xl" />
          </div>
        ) : error ? (
          <WorkSectionErrorCard
            title="Model unavailable"
            message={error instanceof Error ? error.message : "Unknown error"}
            error={error}
            onRetry={() => mutate()}
          />
        ) : model ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"
            >
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Brain className="h-5 w-5 text-emerald-500" />
                  <h1 className="text-2xl font-semibold tracking-tight">{model.name}</h1>
                  <Badge
                    variant="outline"
                    className={cn("capitalize", statusStyles[model.status] ?? statusStyles.draft)}
                  >
                    {model.status}
                  </Badge>
                </div>
                {model.description ? (
                  <p className="max-w-2xl text-sm text-muted-foreground">{model.description}</p>
                ) : null}
              </div>
              <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
                <RefreshCw className={cn("mr-1 h-4 w-4", isValidating && "animate-spin")} />
                Refresh
              </Button>
            </motion.div>

            <ModelDetailInsights
              model={model}
              baseModelOption={baseModelOption}
              connectedDataSources={dataSources}
              canDeploy={Boolean(canDeploy)}
              isDeploying={isDeploying}
              onDeploy={() => void handleDeploy()}
              inferenceJson={inferenceJson}
              onInferenceJsonChange={setInferenceJson}
              isPredicting={isPredicting}
              predictResult={predictResult}
              predictError={predictError}
              onRunInference={() => void handleRunInference()}
              onResetInferenceSample={handleResetInferenceSample}
            />
          </>
        ) : null}
        </div>
      </div>
    </AppShell>
  )
}
