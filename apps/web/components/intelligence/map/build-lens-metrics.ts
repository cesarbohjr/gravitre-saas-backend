import type { IntelligenceLensMetrics } from "./intelligence-map-lens"
import { readNumber } from "@/lib/intelligence/helpers"
import {
  isSnapshotMetricsReady,
  type SnapshotLoadState,
} from "@/lib/intelligence/snapshot-state"

const LOADING_METRICS: IntelligenceLensMetrics = {
  knows: { value: "—", hint: "Loading intelligence…" },
  learns: { value: "—", hint: "Loading intelligence…" },
  predicts: { value: "—", hint: "Loading intelligence…" },
  acts: { value: "—", hint: "Loading intelligence…" },
  improves: { value: "—", hint: "Loading intelligence…" },
}

const ERROR_METRICS: IntelligenceLensMetrics = {
  knows: { value: "—", hint: "Unable to load intelligence" },
  learns: { value: "—", hint: "Unable to load intelligence" },
  predicts: { value: "—", hint: "Unable to load intelligence" },
  acts: { value: "—", hint: "Unable to load intelligence" },
  improves: { value: "—", hint: "Unable to load intelligence" },
}

function formatMetricValue(
  raw: number | null | undefined,
  ready: boolean,
): string {
  if (!ready) return "—"
  if (raw == null) return "—"
  return String(raw)
}

function formatLocaleMetricValue(
  raw: number | null | undefined,
  ready: boolean,
): string {
  if (!ready) return "—"
  if (raw == null) return "—"
  return raw.toLocaleString()
}

export function buildLensMetrics({
  knowledgeGraph,
  readiness,
  modelCatalog,
  coreState,
  businessImpact,
  outcomesByEvent,
  canonicalMetrics,
  loadState = "READY",
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
  /** I1 — UNKNOWN ≠ ZERO: hold placeholders until snapshot is committed. */
  loadState?: SnapshotLoadState
}): IntelligenceLensMetrics {
  if (loadState === "UNINITIALIZED" || loadState === "LOADING") {
    return LOADING_METRICS
  }
  if (loadState === "ERROR") {
    return ERROR_METRICS
  }

  const ready = isSnapshotMetricsReady(loadState)
  const hasCanonical = canonicalMetrics != null && ready
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const predictingLive = Object.values(orgTraining).filter((row) => row?.artifact_loaded).length
  const trackedModels = Object.keys(orgTraining).length
  const entityCount = hasCanonical
    ? canonicalMetrics!.knowledge?.knownEntities
    : ready
      ? knowledgeGraph?.entity_count
      : undefined
  const relationshipCount = hasCanonical
    ? canonicalMetrics!.knowledge?.knownRelationships
    : ready
      ? knowledgeGraph?.relationship_count
      : undefined
  const configuredActive = hasCanonical
    ? canonicalMetrics!.execution?.configuredActiveAgents
    : undefined
  const currentlyRunning = hasCanonical
    ? canonicalMetrics!.execution?.currentlyRunningAgents
    : undefined
  const activeRuns = hasCanonical ? undefined : ready ? coreState?.core?.activeAgentRuns : undefined
  const actionsTaken = ready
    ? readNumber(
        canonicalMetrics?.execution?.actionsCompleted ??
          (hasCanonical ? undefined : outcomesByEvent?.recommendation_created),
        0,
      )
    : 0
  const activePredictions = hasCanonical
    ? canonicalMetrics!.predictions?.activePredictions
    : undefined
  const recentLearnings = hasCanonical
    ? canonicalMetrics!.learning?.recentLearnings
    : undefined
  const measuredOutcomes = hasCanonical
    ? canonicalMetrics!.outcomes?.measuredOutcomes
    : undefined
  const impactScore = ready ? businessImpact?.businessImpactScore : undefined
  const winRate = ready ? businessImpact?.avgOutcomeWinRate : undefined

  const actsValue =
    configuredActive != null
      ? String(configuredActive)
      : activeRuns != null
        ? String(activeRuns)
        : "—"
  const actsHint =
    configuredActive != null && currentlyRunning != null
      ? `${currentlyRunning} running · ${configuredActive} configured active`
      : actionsTaken > 0
        ? `${actionsTaken} actions completed`
        : "Configured active agents (not swarm run count)"

  const refreshHint =
    loadState === "REFRESHING" ? "Refreshing…" : undefined

  return {
    knows: {
      value: formatLocaleMetricValue(entityCount ?? null, ready && (hasCanonical || entityCount != null)),
      hint:
        refreshHint ??
        (relationshipCount != null
          ? `${relationshipCount.toLocaleString()} relationships`
          : entityCount != null
            ? "Entities in knowledge graph"
            : "Graph not populated"),
    },
    learns: {
      value: formatMetricValue(recentLearnings ?? null, ready && hasCanonical),
      hint:
        refreshHint ??
        (recentLearnings != null
          ? "Business learning insights"
          : hasCanonical
            ? "No business learning yet"
            : "Awaiting canonical state"),
    },
    predicts: {
      value: formatMetricValue(activePredictions ?? null, ready && hasCanonical),
      hint:
        refreshHint ??
        (activePredictions != null
          ? "Deduped business predictions"
          : hasCanonical
            ? "No active predictions in window"
            : trackedModels > 0
              ? `${predictingLive} models with artifacts`
              : "Awaiting canonical state"),
    },
    acts: {
      value: actsValue,
      hint: refreshHint ?? actsHint,
    },
    improves: {
      value:
        measuredOutcomes != null
          ? String(measuredOutcomes)
          : impactScore != null
            ? String(Math.round(impactScore))
            : "—",
      hint:
        refreshHint ??
        (measuredOutcomes != null
          ? "Measured outcomes in window"
          : winRate != null
            ? `${Math.round(winRate * 100)}% win rate`
            : businessImpact?.scoreLabel ?? "No outcomes yet"),
    },
  }
}
