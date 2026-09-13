import type { IntelligenceLensMetrics } from "./intelligence-map-lens"
import { readNumber } from "@/lib/intelligence/helpers"
import { summarizeTrainingReadiness } from "@/components/intelligence/training-readiness-strip"

export function buildLensMetrics({
  knowledgeGraph,
  readiness,
  modelCatalog,
  coreState,
  businessImpact,
  outcomesByEvent,
}: {
  knowledgeGraph: { entity_count?: number; relationship_count?: number } | null | undefined
  readiness: Record<string, unknown> | null | undefined
  modelCatalog: { orgTrainingStatus?: Record<string, { artifact_loaded?: boolean }> } | null | undefined
  coreState: { core?: { activeAgentRuns?: number } } | null | undefined
  businessImpact:
    | { businessImpactScore?: number; scoreLabel?: string; avgOutcomeWinRate?: number | null }
    | null
    | undefined
  outcomesByEvent: Record<string, number> | null | undefined
}): IntelligenceLensMetrics {
  const readinessSummary = summarizeTrainingReadiness(readiness)
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const predictingLive = Object.values(orgTraining).filter((row) => row?.artifact_loaded).length
  const trackedModels = Object.keys(orgTraining).length
  const entityCount = knowledgeGraph?.entity_count
  const relationshipCount = knowledgeGraph?.relationship_count
  const activeRuns = coreState?.core?.activeAgentRuns
  const actionsTaken = readNumber(outcomesByEvent?.recommendation_created, 0)
  const impactScore = businessImpact?.businessImpactScore
  const winRate = businessImpact?.avgOutcomeWinRate

  return {
    knows: {
      value: entityCount != null ? entityCount.toLocaleString() : "—",
      hint:
        relationshipCount != null
          ? `${relationshipCount.toLocaleString()} relationships`
          : "Graph not populated",
    },
    learns: {
      value: readinessSummary.total > 0 ? String(readinessSummary.ready) : "—",
      hint: readinessSummary.total > 0 ? `${readinessSummary.total} models tracked` : "No training signals",
    },
    predicts: {
      value: trackedModels > 0 ? String(predictingLive) : "—",
      hint: trackedModels > 0 ? `of ${trackedModels} in catalog` : "No catalog models",
    },
    acts: {
      value: activeRuns != null ? String(activeRuns) : "—",
      hint: actionsTaken > 0 ? `${actionsTaken} recommendations` : "Active runs, 24h",
    },
    improves: {
      value: impactScore != null ? String(Math.round(impactScore)) : "—",
      hint:
        winRate != null
          ? `${Math.round(winRate * 100)}% win rate`
          : businessImpact?.scoreLabel ?? "No outcomes yet",
    },
  }
}
