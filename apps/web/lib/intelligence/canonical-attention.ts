/**
 * G6 — Map canonical predictions to customer-facing attention rows (deduped at source).
 */
import { readString } from "@/lib/intelligence/helpers"

export type CanonicalPredictionRow = {
  id?: string
  businessStatement?: string
  department?: string | null
  confidence?: number | null
  qualityFlags?: string[]
  status?: string
}

export type AttentionSignalRow = Record<string, unknown>

function predictionScore(row: CanonicalPredictionRow): number {
  const confidence = Number(row.confidence)
  if (Number.isFinite(confidence)) return confidence
  const flags = row.qualityFlags ?? []
  if (flags.includes("UNSCOPED_PREDICTION")) return 0.55
  if (flags.includes("INSUFFICIENT_EVIDENCE")) return 0.45
  return 0.35
}

/** Convert deduped canonical predictions into ranked attention cards. */
export function canonicalPredictionsToAttentionSignals(
  predictions: CanonicalPredictionRow[] | null | undefined,
  max = 5,
): AttentionSignalRow[] {
  if (!predictions?.length) return []

  return [...predictions]
    .sort((a, b) => predictionScore(b) - predictionScore(a))
    .slice(0, max)
    .map((row) => {
      const id = readString(row.id, "")
      const confidence = Number(row.confidence)
      return {
        id,
        title: readString(row.businessStatement, "Prediction"),
        summary: row.department ? `Department: ${row.department}` : "",
        department: row.department,
        confidence: Number.isFinite(confidence) ? confidence : null,
        quality_score: Number.isFinite(confidence) ? confidence * 100 : null,
        qualityFlags: row.qualityFlags ?? [],
        source: "canonical_prediction",
      }
    })
}

export type CanonicalLearningRow = {
  id?: string
  businessStatement?: string
  learnedAt?: string | null
  confidence?: string | null
}

export function canonicalLearningsForDisplay(
  learnings: CanonicalLearningRow[] | null | undefined,
  max = 3,
): Array<{ id: string; statement: string; learnedAt?: string; confidence?: string }> {
  if (!learnings?.length) return []
  return learnings.slice(0, max).map((row, index) => ({
    id: readString(row.id, `learning-${index}`),
    statement: readString(row.businessStatement, "Business learning insight"),
    learnedAt: row.learnedAt ?? undefined,
    confidence: row.confidence ?? undefined,
  }))
}
