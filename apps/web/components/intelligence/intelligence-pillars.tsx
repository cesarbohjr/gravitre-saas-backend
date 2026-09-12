"use client"

/**
 * Intelligence redesign, brief-Phase 3 (2026-09-11) — Overview business-
 * friendly summary: KNOWS / LEARNS / PREDICTS / ACTS / IMPROVES. Every
 * number is read from a real endpoint already used elsewhere in the
 * product; when a source has no data yet, the card shows "—" rather than
 * a fabricated figure. See docs/delivery/gravitre-intelligence-redesign-
 * phase0-proposal-2026-09-11.md §17 for the source mapping.
 */

import useSWR from "swr"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { intelligenceApi } from "@/lib/api"
import { APP_ROUTES, LEGACY_APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { readNumber } from "@/lib/intelligence/helpers"
import { summarizeTrainingReadiness } from "@/components/intelligence/training-readiness-strip"
import { cn } from "@/lib/utils"
import { Brain, Lightning, PottedPlant, Pulse, Target } from "@phosphor-icons/react"

export function useIntelligencePillarsData(enabled: boolean) {
  const knowledgeGraph = useSWR(
    enabled ? "intelligence/overview/knowledge-graph" : null,
    () => intelligenceApi.knowledgeGraph(),
    { revalidateOnFocus: false },
  )
  const coreState = useSWR(
    enabled ? ["intelligence/core-state", 24] : null,
    () => intelligenceApi.coreState({ windowHours: 24 }),
    { revalidateOnFocus: false, refreshInterval: 20_000 },
  )
  const businessImpact = useSWR(
    enabled ? "intelligence/overview/business-impact" : null,
    () => intelligenceApi.businessImpact(),
    { revalidateOnFocus: false },
  )
  return { knowledgeGraph, coreState, businessImpact }
}

export function IntelligencePillars({
  readiness,
  modelCatalog,
  outcomesByEvent,
  knowledgeGraph,
  coreState,
  businessImpact,
  className,
}: {
  readiness: Record<string, unknown> | null | undefined
  modelCatalog: { orgTrainingStatus?: Record<string, { artifact_loaded?: boolean }> } | null | undefined
  outcomesByEvent: Record<string, number> | null | undefined
  knowledgeGraph:
    | { entity_count?: number; relationship_count?: number }
    | null
    | undefined
  coreState: { core?: { activeAgentRuns?: number } } | null | undefined
  businessImpact:
    | { businessImpactScore?: number; scoreLabel?: string; avgOutcomeWinRate?: number | null }
    | null
    | undefined
  className?: string
}) {
  const readinessSummary = summarizeTrainingReadiness(readiness)
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const predictingLive = Object.values(orgTraining).filter((row) => row?.artifact_loaded).length
  const trackedModels = Object.keys(orgTraining).length

  const entityCount = knowledgeGraph?.entity_count
  const relationshipCount = knowledgeGraph?.relationship_count
  const activeRuns = coreState?.core?.activeAgentRuns
  const actionsTaken = readNumber(outcomesByEvent?.recommendation_created, 0)

  // businessImpactScore is already 0-100 (see backend business_impact_service.py
  // `max(0, min(100, 100 - penalty))`) -- do not multiply by 100 again.
  // avgOutcomeWinRate is a 0-1 fraction -- multiply by 100 for a percent.
  const impactScore = businessImpact?.businessImpactScore
  const winRate = businessImpact?.avgOutcomeWinRate

  return (
    <section
      className={cn("relative", className)}
      aria-labelledby="intelligence-pillars-heading"
      data-intelligence-pillars=""
    >
      <p className={TYPE.eyebrow}>In plain terms</p>
      <h2 id="intelligence-pillars-heading" className={TYPE.sectionTitle}>
        What the system knows, learns, predicts, acts on, and improves
      </h2>
      <div className="mt-3 grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-5">
        <GravitreMetric
          label="Knows"
          value={entityCount != null ? entityCount.toLocaleString() : "—"}
          hint={
            relationshipCount != null
              ? `${relationshipCount.toLocaleString()} relationships mapped`
              : "Knowledge graph not populated yet"
          }
          icon={<Brain className="h-4 w-4" weight="duotone" aria-hidden />}
          href={APP_ROUTES.intelligenceMemory}
        />
        <GravitreMetric
          label="Learns"
          value={readinessSummary.total > 0 ? readinessSummary.ready : "—"}
          hint={
            readinessSummary.total > 0
              ? `${readinessSummary.total} models tracked`
              : "No training signals yet"
          }
          icon={<PottedPlant className="h-4 w-4" weight="duotone" aria-hidden />}
          href={APP_ROUTES.training}
        />
        <GravitreMetric
          label="Predicts"
          value={trackedModels > 0 ? predictingLive : "—"}
          hint={trackedModels > 0 ? `of ${trackedModels} in catalog` : "No models in catalog yet"}
          icon={<Target className="h-4 w-4" weight="duotone" aria-hidden />}
          href={LEGACY_APP_ROUTES.intelligenceModelsPath}
        />
        <GravitreMetric
          label="Acts"
          value={activeRuns != null ? activeRuns : "—"}
          hint={actionsTaken > 0 ? `${actionsTaken} recommendations this period` : "Active runs, last 24h"}
          icon={<Lightning className="h-4 w-4" weight="duotone" aria-hidden />}
          href={APP_ROUTES.agents}
        />
        <GravitreMetric
          label="Improves"
          value={impactScore != null ? Math.round(impactScore) : "—"}
          hint={
            winRate != null
              ? `${Math.round(winRate * 100)}% avg outcome win rate`
              : businessImpact?.scoreLabel ?? "No outcome history yet"
          }
          icon={<Pulse className="h-4 w-4" weight="duotone" aria-hidden />}
          href={APP_ROUTES.learning}
        />
      </div>
    </section>
  )
}
