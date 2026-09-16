/**
 * I8 — Business catalog formatting for registry models.
 */
import { modelTypeMeta } from "@/lib/ml-registry-catalog"
import { describeStatus } from "@/lib/intelligence/status-language"
import type { MlModelSummary } from "@/types/api"

export type ModelCatalogView = "business" | "technical"

export type ModelCatalogDisplay = {
  id: string
  name: string
  purpose: string
  businessStatus: string
  businessStatusDetail: string
  whereUsed: string
  performance: string
  learningSources: string[]
  lastUpdatedLabel?: string
  recommendedImprovement: string
  architecture: string
  datasetId?: string
  baseModel?: string
  versionLabel: string
  technicalStatus: string
  href: string
}

export function recommendedImprovementForStatus(status: string | null | undefined): string {
  const key = String(status ?? "").trim().toLowerCase()
  if (key === "draft" || key === "untrained" || key === "not_trained") {
    return "Add training data in Model Studio, then run a job."
  }
  if (key === "training" || key === "fine_tuning") {
    return "Wait for the current run to finish, then evaluate before deploy."
  }
  if (key === "validating" || key === "evaluating") {
    return "Review evaluation results, then deploy if they meet your bar."
  }
  if (key === "ready") {
    return "Deploy a version so agents and workflows can call it."
  }
  if (key === "failed") {
    return "Open Model Studio Runs to inspect the failed job and retry."
  }
  if (key === "deployed") {
    return "Monitor live use; retrain from Model Studio when results drift."
  }
  if (key === "stale") {
    return "Retrain with newer examples in Model Studio."
  }
  return describeStatus(status).detail
}

export function whereUsedLabel(model: MlModelSummary): string {
  if (model.deployedVersion != null || model.status === "deployed") {
    return "Available to workflows and agents"
  }
  return "Not in production use yet"
}

export function formatModelCatalogRow(model: MlModelSummary): ModelCatalogDisplay {
  const meta = modelTypeMeta(model.modelType)
  const status = describeStatus(model.status)
  const updated = model.updatedAt || model.createdAt
  let lastUpdatedLabel: string | undefined
  if (updated) {
    const parsed = Date.parse(updated)
    lastUpdatedLabel = Number.isNaN(parsed)
      ? updated
      : new Date(parsed).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
  }

  const learningSources: string[] = []
  if (model.datasetId) learningSources.push("Training dataset")
  if (model.baseModel) learningSources.push(model.baseModel)

  return {
    id: model.id,
    name: model.name,
    purpose: (model.description || "").trim() || meta?.tagline || "Registered model",
    businessStatus: status.phrase,
    businessStatusDetail: status.detail,
    whereUsed: whereUsedLabel(model),
    performance:
      model.deployedVersion != null
        ? `Live version ${model.deployedVersion}`
        : `Registry version ${model.currentVersion}`,
    learningSources,
    lastUpdatedLabel,
    recommendedImprovement: recommendedImprovementForStatus(model.status),
    architecture: meta?.label ?? model.modelType.replace(/_/g, " "),
    datasetId: model.datasetId ?? undefined,
    baseModel: model.baseModel ?? undefined,
    versionLabel: `v${model.currentVersion}`,
    technicalStatus: model.status,
    href: `/models/${model.id}`,
  }
}

export const STUDIO_INTENTS = [
  {
    id: "predict",
    label: "Predict outcome",
    description: "Score or forecast a business result from connected data.",
    modelType: "classifier" as const,
  },
  {
    id: "classify",
    label: "Classify / score",
    description: "Route, grade, or rank records with a classifier.",
    modelType: "classifier" as const,
  },
  {
    id: "anomaly",
    label: "Detect anomaly",
    description: "Flag unusual spikes, drift, or incidents.",
    modelType: "anomaly_detector" as const,
  },
  {
    id: "forecast",
    label: "Forecast",
    description: "Project volume, revenue, or capacity forward.",
    modelType: "forecaster" as const,
  },
  {
    id: "improve_agent",
    label: "Improve agent",
    description: "Fine-tune an assistant on your examples and tone.",
    modelType: "fine_tuned_llm" as const,
  },
  {
    id: "advanced",
    label: "Advanced / custom",
    description: "Register a model with full type and base-model controls.",
    modelType: "fine_tuned_llm" as const,
  },
] as const

export type StudioIntentId = (typeof STUDIO_INTENTS)[number]["id"]

export function studioIntentById(id: string | null | undefined) {
  return STUDIO_INTENTS.find((item) => item.id === id) ?? null
}

export const STUDIO_SEGMENTS = [
  { id: "create", label: "Create" },
  { id: "train", label: "Train" },
  { id: "evaluate", label: "Evaluate" },
  { id: "deploy", label: "Deploy" },
  { id: "runs", label: "Runs" },
] as const

export type StudioSegment = (typeof STUDIO_SEGMENTS)[number]["id"]
