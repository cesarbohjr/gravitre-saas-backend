/**
 * I6 — Format canonical predictions for customer Predictions hub.
 */
import { readString } from "@/lib/intelligence/helpers"
import { qualityFlagToCopy } from "@/lib/intelligence/quality-copy"

export type PredictionKind = "risk" | "opportunity" | "signal"

export type BusinessPredictionDisplay = {
  id: string
  statement: string
  kind: PredictionKind
  horizon?: string
  confidence?: number | null
  drivers: string[]
  impact?: string
  evidence: string[]
  actions: string[]
  department?: string
  qualityNotes: string[]
  isUnscoped: boolean
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
}

export function classifyPredictionKind(type: unknown): PredictionKind {
  const normalized = readString(type, "prediction").toLowerCase()
  if (normalized === "risk" || normalized === "alert") return "risk"
  if (normalized === "opportunity") return "opportunity"
  return "signal"
}

export function formatPredictionRow(row: Record<string, unknown>): BusinessPredictionDisplay {
  const qualityFlags = readStringArray(row.qualityFlags as unknown)
  const drivers: string[] = []
  const objective = readString(row.objective, "")
  const subject = readString(row.subject, "")
  const sourceModel = readString(row.sourceModel, "")
  if (objective) drivers.push(objective)
  if (subject && subject !== objective) drivers.push(subject)
  if (sourceModel) drivers.push(`Model: ${sourceModel}`)

  const horizon = readString(row.horizon, "") || undefined
  const department = readString(row.department, "") || undefined
  const confidenceRaw = row.confidence
  const confidence =
    confidenceRaw === null || confidenceRaw === undefined
      ? null
      : Number.isFinite(Number(confidenceRaw))
        ? Number(confidenceRaw)
        : null

  return {
    id: readString(row.id, readString(row.semanticKey, "prediction").slice(0, 16)),
    statement: readString(row.businessStatement, "Business prediction"),
    kind: classifyPredictionKind(row.type),
    horizon,
    confidence,
    drivers,
    impact: objective || undefined,
    evidence: readStringArray(row.evidence),
    actions: readStringArray(row.recommendedActions),
    department,
    qualityNotes: qualityFlags.map(qualityFlagToCopy),
    isUnscoped: qualityFlags.includes("UNSCOPED_PREDICTION"),
  }
}

export function formatPredictions(
  rows: Record<string, unknown>[] | null | undefined,
): BusinessPredictionDisplay[] {
  if (!rows?.length) return []
  return rows.map((row) => formatPredictionRow(row))
}

export function partitionPredictionsByKind(predictions: BusinessPredictionDisplay[]): {
  risks: BusinessPredictionDisplay[]
  opportunities: BusinessPredictionDisplay[]
  signals: BusinessPredictionDisplay[]
} {
  const risks: BusinessPredictionDisplay[] = []
  const opportunities: BusinessPredictionDisplay[] = []
  const signals: BusinessPredictionDisplay[] = []
  for (const row of predictions) {
    if (row.kind === "risk") risks.push(row)
    else if (row.kind === "opportunity") opportunities.push(row)
    else signals.push(row)
  }
  return { risks, opportunities, signals }
}

export function filterPredictionsByDepartment(
  predictions: BusinessPredictionDisplay[],
  department: string | null,
): BusinessPredictionDisplay[] {
  if (!department || department === "all") return predictions
  const needle = department.replace("_", " ").toLowerCase()
  return predictions.filter((row) => {
    const dept = (row.department ?? "").toLowerCase().replace("_", " ")
    return !dept || dept.includes(needle) || needle.includes(dept)
  })
}
