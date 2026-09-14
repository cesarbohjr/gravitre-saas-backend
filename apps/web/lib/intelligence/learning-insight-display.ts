/**
 * G7 — Format canonical LearningInsight rows for customer Learning hub.
 */
import { readString } from "@/lib/intelligence/helpers"

export type LearningInsightDisplay = {
  id: string
  statement: string
  learnedAt?: string
  learnedAtLabel?: string
  learnedFrom: string[]
  evidence: string[]
  affectedEntities: string[]
  resultingChanges: string[]
  confidence?: string
  provenance?: string
}

function provenanceLabel(source: unknown): string | undefined {
  if (!source || typeof source !== "object") return undefined
  const record = source as Record<string, unknown>
  const system = readString(record.system, "")
  if (!system) return undefined
  const recordId = readString(record.recordId, "")
  return recordId ? `${system} · ${recordId}` : system
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
}

export function formatLearningInsightRow(row: Record<string, unknown>): LearningInsightDisplay {
  const learnedAt = readString(row.learnedAt, "")
  let learnedAtLabel: string | undefined
  if (learnedAt) {
    const parsed = Date.parse(learnedAt)
    learnedAtLabel = Number.isNaN(parsed)
      ? learnedAt
      : new Date(parsed).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
  }

  return {
    id: readString(row.id, readString(row.businessStatement, "learning").slice(0, 32)),
    statement: readString(row.businessStatement, "Learning insight"),
    learnedAt: learnedAt || undefined,
    learnedAtLabel,
    learnedFrom: readStringArray(row.learnedFrom),
    evidence: readStringArray(row.evidence),
    affectedEntities: readStringArray(row.affectedEntities),
    resultingChanges: readStringArray(row.resultingChanges),
    confidence: readString(row.confidence, "") || undefined,
    provenance: provenanceLabel(row.source),
  }
}

export function formatLearningInsights(
  rows: Record<string, unknown>[] | null | undefined,
): LearningInsightDisplay[] {
  if (!rows?.length) return []
  return rows.map((row) => formatLearningInsightRow(row))
}
