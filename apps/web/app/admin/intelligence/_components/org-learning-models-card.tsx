"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { mlAdminApi, type MlAdminTrainResult, type MlAdminOrgModelStatus } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import {
  ORG_LEARNING_MODEL_IDS,
  ORG_LEARNING_TRAIN_MODELS,
  type OrgLearningModelId,
} from "@/lib/org-learning-models"
import { cn } from "@/lib/utils"
import { Brain, Lightning, SpinnerGap } from "@phosphor-icons/react"

function readDataCount(status: MlAdminOrgModelStatus | undefined): string | null {
  if (!status?.data_counts) return null
  const counts = status.data_counts
  const first = Object.entries(counts)[0]
  if (!first) return null
  const [key, value] = first
  return `${value} ${key.replace(/_/g, " ")}`
}

function trainResultMessage(result: MlAdminTrainResult): string {
  if (result.temporal) {
    return "Training queued in the background workflow."
  }
  if (result.trained) {
    return "Model trained and artifact saved."
  }
  if (result.reason === "insufficient_data") {
    const parts: string[] = []
    if (typeof result.query_rows === "number" && typeof result.required === "number") {
      parts.push(`${result.query_rows}/${result.required} queries`)
    }
    if (typeof result.distinct_queries === "number" && typeof result.required === "number") {
      parts.push(`${result.distinct_queries}/${result.required} distinct queries`)
    }
    if (typeof result.resolved_candidates === "number" && typeof result.required === "number") {
      parts.push(`${result.resolved_candidates}/${result.required} resolved candidates`)
    }
    if (typeof result.training_examples === "number" && typeof result.required === "number") {
      parts.push(`${result.training_examples}/${result.required} training examples`)
    }
    return parts.length > 0
      ? `Not enough data yet (${parts.join(", ")}).`
      : "Not enough org data to train yet."
  }
  return "Training finished without a new artifact."
}

export function OrgLearningModelsCard({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? "admin/ml/models" : null,
    () => mlAdminApi.listCatalog(),
    { revalidateOnFocus: false },
  )

  const [pendingModel, setPendingModel] = useState<OrgLearningModelId | "all" | null>(null)

  const statusByModel = useMemo(() => {
    const map = new Map<string, MlAdminOrgModelStatus>()
    for (const [name, status] of Object.entries(data?.orgTrainingStatus ?? {})) {
      map.set(name, status)
    }
    return map
  }, [data?.orgTrainingStatus])

  async function trainOne(modelId: OrgLearningModelId): Promise<MlAdminTrainResult> {
    return mlAdminApi.trainModel(modelId)
  }

  async function handleTrain(modelId: OrgLearningModelId) {
    setPendingModel(modelId)
    try {
      const result = await trainOne(modelId)
      if (result.trained || result.temporal) {
        toast.success(`${modelId.replace(/_/g, " ")}`, { description: trainResultMessage(result) })
      } else {
        toast.message(`${modelId.replace(/_/g, " ")}`, { description: trainResultMessage(result) })
      }
      await mutate()
    } catch (trainError) {
      toast.error(
        trainError instanceof ApiError ? trainError.message : "Training request failed",
      )
    } finally {
      setPendingModel(null)
    }
  }

  async function handleRetrainAll() {
    setPendingModel("all")
    let trainedCount = 0
    let skippedCount = 0
    try {
      for (const modelId of ORG_LEARNING_MODEL_IDS) {
        const result = await trainOne(modelId)
        if (result.trained || result.temporal) {
          trainedCount += 1
        } else {
          skippedCount += 1
        }
      }
      await mutate()
      if (trainedCount > 0) {
        toast.success("Retrain all complete", {
          description: `${trainedCount} model${trainedCount === 1 ? "" : "s"} trained or queued${skippedCount > 0 ? `; ${skippedCount} skipped (insufficient data).` : "."}`,
        })
      } else {
        toast.message("Retrain all finished", {
          description: "No models had enough data to train. Check progress in Overview and Evaluation.",
        })
      }
    } catch (trainError) {
      toast.error(
        trainError instanceof ApiError ? trainError.message : "Retrain all failed",
      )
    } finally {
      setPendingModel(null)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Brain className="h-5 w-5 text-violet-500" weight="duotone" aria-hidden />
              <CardTitle>Org learning models</CardTitle>
            </div>
            <CardDescription>
              Retrain automatic intelligence models from this org&apos;s usage data. These are separate
              from Agent Training (fine-tunes) and Model Registry (production deploy).
            </CardDescription>
          </div>
          <Button
            variant="default"
            size="sm"
            disabled={pendingModel !== null || isLoading}
            onClick={() => void handleRetrainAll()}
          >
            {pendingModel === "all" ? (
              <SpinnerGap className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Lightning className="mr-2 h-4 w-4" weight="duotone" aria-hidden />
            )}
            Retrain all
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {error ? (
          <p className="text-sm text-destructive">
            {error instanceof ApiError ? error.message : "Could not load model catalog."}
          </p>
        ) : isLoading ? (
          <p className="text-sm text-muted-foreground">Loading org learning models…</p>
        ) : (
          ORG_LEARNING_TRAIN_MODELS.map((model) => {
            const status = statusByModel.get(model.id)
            const dataLabel = readDataCount(status)
            const isPending = pendingModel === model.id || pendingModel === "all"
            return (
              <div
                key={model.id}
                className="flex flex-col gap-3 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-foreground">{model.label}</span>
                    <Badge variant="outline" className="text-[10px] uppercase">
                      {model.version}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground text-pretty">{model.description}</p>
                  <p className="text-xs text-muted-foreground">
                    Needs {model.dataHint}
                    {dataLabel ? (
                      <>
                        {" "}
                        · current: <span className="tabular-nums text-foreground">{dataLabel}</span>
                      </>
                    ) : null}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn("shrink-0", isPending && "pointer-events-none opacity-70")}
                  disabled={pendingModel !== null}
                  onClick={() => void handleTrain(model.id)}
                >
                  {isPending ? (
                    <SpinnerGap className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  ) : null}
                  Train
                </Button>
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
