import type { IntelligenceLensMetrics } from "./intelligence-map-lens"
import { readNumber } from "@/lib/intelligence/helpers"
export function buildLensMetrics({
  knowledgeGraph,
  readiness,
  modelCatalog,
  coreState,
  businessImpact,
  outcomesByEvent,
  canonicalMetrics,
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
  /** G1 — when present, lens bar uses canonical typed metrics instead of legacy sources. */
  canonicalMetrics?: {
    knowledge?: Record<string, number | null | undefined>
    learning?: Record<string, number | null | undefined>
    predictions?: Record<string, number | null | undefined>
    execution?: Record<string, number | null | undefined>
    outcomes?: Record<string, number | null | undefined>
  } | null
}): IntelligenceLensMetrics {
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const predictingLive = Object.values(orgTraining).filter((row) => row?.artifact_loaded).length
  const trackedModels = Object.keys(orgTraining).length
  const entityCount = canonicalMetrics?.knowledge?.knownEntities ?? knowledgeGraph?.entity_count
  const relationshipCount =
    canonicalMetrics?.knowledge?.knownRelationships ?? knowledgeGraph?.relationship_count
  const configuredActive = canonicalMetrics?.execution?.configuredActiveAgents
  const currentlyRunning = canonicalMetrics?.execution?.currentlyRunningAgents
  const activeRuns = coreState?.core?.activeAgentRuns
  const actionsTaken = readNumber(
    canonicalMetrics?.execution?.actionsCompleted ?? outcomesByEvent?.recommendation_created,
    0,
  )
  const activePredictions = canonicalMetrics?.predictions?.activePredictions
  const recentLearnings = canonicalMetrics?.learning?.recentLearnings
  const measuredOutcomes = canonicalMetrics?.outcomes?.measuredOutcomes
  const impactScore = businessImpact?.businessImpactScore
  const winRate = businessImpact?.avgOutcomeWinRate

  const actsValue =
    configuredActive != null
      ? String(configuredActive)
      : activeRuns != null
        ? String(activeRuns)
        : "—"
  const actsHint =
    configuredActive != null && currentlyRunning != null
      ? `${currentlyRunning} running now`
      : actionsTaken > 0
        ? `${actionsTaken} actions completed`
        : "Configured active agents"

  return {
    knows: {
      value: entityCount != null ? entityCount.toLocaleString() : "—",
      hint:
        relationshipCount != null
          ? `${relationshipCount.toLocaleString()} relationships`
          : "Graph not populated",
    },
    learns: {
      value: recentLearnings != null ? String(recentLearnings) : "—",
      hint:
        recentLearnings != null
          ? "Business learning insights"
          : "No business learning yet",
    },
    predicts: {
      value:
        activePredictions != null
          ? String(activePredictions)
          : trackedModels > 0
            ? String(predictingLive)
            : "—",
      hint:
        activePredictions != null
          ? "Deduped predictions"
          : trackedModels > 0
            ? `of ${trackedModels} in catalog`
            : "No catalog models",
    },
    acts: {
      value: actsValue,
      hint: actsHint,
    },
    improves: {
      value:
        measuredOutcomes != null
          ? String(measuredOutcomes)
          : impactScore != null
            ? String(Math.round(impactScore))
            : "—",
      hint:
        measuredOutcomes != null
          ? "Measured outcomes in window"
          : winRate != null
            ? `${Math.round(winRate * 100)}% win rate`
            : businessImpact?.scoreLabel ?? "No outcomes yet",
    },
  }
}
