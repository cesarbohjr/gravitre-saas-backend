/**
 * I5 — Client-side filters for Learning hub insights (Learned Recently segment).
 */
import type { LearningInsightDisplay } from "@/lib/intelligence/learning-insight-display"

export type LearningSegment = "recent" | "relationships" | "memory" | "models"

export type EvidenceQualityFilter = "all" | "verified" | "needs_evidence"
export type ConfidenceFilter = "all" | string
export type SourceFilter = "all" | string
export type TimeRangeFilter = "all" | "7d" | "30d" | "90d"

export type LearningInsightFilters = {
  evidenceQuality: EvidenceQualityFilter
  confidence: ConfidenceFilter
  source: SourceFilter
  timeRange: TimeRangeFilter
}

export const DEFAULT_LEARNING_FILTERS: LearningInsightFilters = {
  evidenceQuality: "all",
  confidence: "all",
  source: "all",
  timeRange: "all",
}

const MS_DAY = 86_400_000

function timeRangeCutoff(range: TimeRangeFilter): number | null {
  if (range === "all") return null
  const days = range === "7d" ? 7 : range === "30d" ? 30 : 90
  return Date.now() - days * MS_DAY
}

function insightSources(insight: LearningInsightDisplay): string[] {
  const sources = [...insight.learnedFrom]
  if (insight.provenance) {
    const system = insight.provenance.split(" · ")[0]?.trim()
    if (system) sources.push(system)
  }
  return sources.map((s) => s.toLowerCase())
}

export function collectInsightFilterOptions(insights: LearningInsightDisplay[]): {
  confidenceOptions: string[]
  sourceOptions: string[]
} {
  const confidence = new Set<string>()
  const sources = new Set<string>()
  for (const insight of insights) {
    if (insight.confidence?.trim()) confidence.add(insight.confidence.trim())
    for (const src of insightSources(insight)) {
      if (src) sources.add(src)
    }
  }
  return {
    confidenceOptions: [...confidence].sort(),
    sourceOptions: [...sources].sort(),
  }
}

export function filterLearningInsights(
  insights: LearningInsightDisplay[],
  filters: LearningInsightFilters,
): LearningInsightDisplay[] {
  const cutoff = timeRangeCutoff(filters.timeRange)

  return insights.filter((insight) => {
    if (filters.evidenceQuality === "verified" && insight.evidence.length === 0) return false
    if (filters.evidenceQuality === "needs_evidence" && insight.evidence.length > 0) return false

    if (filters.confidence !== "all") {
      const conf = (insight.confidence ?? "").trim()
      if (conf !== filters.confidence) return false
    }

    if (filters.source !== "all") {
      const needle = filters.source.toLowerCase()
      if (!insightSources(insight).some((s) => s === needle || s.includes(needle))) return false
    }

    if (cutoff !== null) {
      if (!insight.learnedAt) return false
      const parsed = Date.parse(insight.learnedAt)
      if (Number.isNaN(parsed) || parsed < cutoff) return false
    }

    return true
  })
}
