"use client"

/**
 * I3 — Living Intelligence Map product surface for Overview.
 * Composes lens strip + graph engine + contextual inspector on the I2 stack.
 */

import { motion, useReducedMotion } from "framer-motion"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import { IntelligenceMap, type IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import { IntelligenceLensBar } from "@/components/intelligence/map/intelligence-lens-bar"
import { IntelligenceInspectorDrawer } from "@/components/intelligence/map/intelligence-inspector-drawer"
import type { IntelligenceLensMetrics } from "@/components/intelligence/map/intelligence-map-lens"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import type { AllDepartmentsPayload } from "@/components/intelligence/why-gravitre-panel"
import type { SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function OverviewLivingMap({
  activeLens,
  onLensChange,
  lensMetrics,
  snapshotLoadState,
  pageContext,
  mapAgents,
  signals,
  entityCount,
  relationshipCount,
  selection,
  onSelectionChange,
  highlightNodeIds,
  dimNodeIds,
  focusNodeIds,
  whyEvidence,
  onAskAbout,
  cacheKey,
  className,
}: {
  activeLens: IntelligenceMapLens
  onLensChange: (lens: IntelligenceMapLens) => void
  lensMetrics: IntelligenceLensMetrics
  snapshotLoadState: SnapshotLoadState
  pageContext?: IntelligencePageContextResponse | null
  mapAgents: Agent[]
  signals: Record<string, unknown>[]
  entityCount?: number | null
  relationshipCount?: number | null
  selection: IntelligenceMapSelection
  onSelectionChange: (selection: IntelligenceMapSelection) => void
  highlightNodeIds: string[]
  dimNodeIds: string[]
  focusNodeIds: string[]
  whyEvidence?: AllDepartmentsPayload | null
  onAskAbout?: (question: string) => void
  cacheKey?: string
  className?: string
}) {
  const reducedMotion = useReducedMotion()
  const mapLoading = !isSnapshotMetricsReady(snapshotLoadState) && snapshotLoadState !== "ERROR"
  const activeLensMeta = {
    knows: "What Gravitre knows about your business",
    learns: "What Gravitre has learned recently",
    predicts: "Forward-looking predictions and risks",
    acts: "Agents and execution in flight",
    improves: "Measured outcomes and improvement loops",
  }[activeLens]

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={TYPE.eyebrow}>Intelligence lenses</p>
          <p className={cn(TYPE.meta, "mt-0.5 max-w-xl")}>{activeLensMeta}</p>
        </div>
        <p className={cn(TYPE.meta, "text-muted-foreground")}>
          Select a lens to transform the map
        </p>
      </div>

      <IntelligenceLensBar
        activeLens={activeLens}
        onLensChange={onLensChange}
        metrics={lensMetrics}
        className="shadow-sm"
      />

      <motion.div
        layout={!reducedMotion}
        className="relative min-h-[56vh] rounded-[var(--np-radius-lg)]"
        transition={{ duration: reducedMotion ? 0 : 0.25 }}
      >
        {mapLoading ? (
          <div
            className="pointer-events-none absolute inset-0 z-30 flex items-center justify-center rounded-[var(--np-radius-lg)] bg-[color:var(--g-surface-1)]/60 backdrop-blur-[2px]"
            aria-live="polite"
            aria-busy="true"
          >
            <div className="space-y-2 text-center">
              <div className="mx-auto h-8 w-8 animate-pulse rounded-full bg-[color:var(--g-intelligence)]/30" />
              <p className={TYPE.meta}>Loading intelligence map…</p>
            </div>
          </div>
        ) : null}

        <IntelligenceMap
          lens={activeLens}
          signals={signals}
          agents={mapAgents}
          entityCount={entityCount}
          relationshipCount={relationshipCount}
          canonicalGraph={pageContext?.graph}
          selection={selection}
          onSelectionChange={onSelectionChange}
          highlightNodeIds={highlightNodeIds}
          dimNodeIds={dimNodeIds}
          focusNodeIds={focusNodeIds}
          cacheKey={cacheKey}
          className="min-h-[56vh]"
        />

        {!selection && !mapLoading ? (
          <p
            className={cn(
              TYPE.meta,
              "pointer-events-none absolute bottom-14 left-1/2 z-20 max-w-sm -translate-x-1/2 rounded-full border border-divide/80 bg-[color:var(--g-surface-1)]/95 px-3 py-1 text-center shadow-sm backdrop-blur-sm",
            )}
          >
            Explore the map — click a node or edge to inspect evidence
          </p>
        ) : null}
      </motion.div>

      <IntelligenceInspectorDrawer
        selection={selection}
        onSelectionChange={onSelectionChange}
        pageContext={pageContext}
        whyData={whyEvidence}
        onAskAbout={onAskAbout}
      />
    </div>
  )
}
