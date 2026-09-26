"use client"

/**
 * UX/UI 3.0 Plus — I3 Matrix (default) + I1 Field + contextual I2 Change Stream
 * Production surface for /intelligence OverviewLivingMap.
 * Uses canonical page-context graph + snapshot events — no fabricated telemetry.
 */

import { useMemo, useState } from "react"
import Link from "next/link"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import { IntelligenceMap, type IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import { IntelligenceInspectorDrawer } from "@/components/intelligence/map/intelligence-inspector-drawer"
import { IntelligenceChangeStream } from "@/components/intelligence/intelligence-change-stream"
import { IntelligenceMatrixLens } from "@/components/intelligence/intelligence-matrix-lens"
import type { IntelligenceLensMetrics } from "@/components/intelligence/map/intelligence-map-lens"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import { INTELLIGENCE_MAP_LENSES } from "@/components/intelligence/map/intelligence-map-lens"
import type { AllDepartmentsPayload } from "@/components/intelligence/why-gravitre-panel"
import type { SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { Button } from "@/components/ui/button"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { buildChangeEvents } from "@/lib/intelligence/build-change-events"
import { resolveOverviewFieldState } from "@/lib/intelligence/overview-field-state"
import type { CanonicalGraphNode } from "@/lib/intelligence/canonical-graph-topology"
import { useGravitreMobileViewport } from "@/hooks/use-gravitre-mobile-viewport"
import { useReducedMotion } from "framer-motion"

const LENS_QUESTIONS: Record<IntelligenceMapLens, string> = {
  knows: "What does Gravitre know about this business?",
  learns: "What has Gravitre learned recently?",
  predicts: "What is Gravitre predicting?",
  acts: "What is Gravitre doing?",
  improves: "What has improved?",
}

type OverviewViewMode = "matrix" | "field"
type MobilePanel = "main" | "changes"

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
  const isMobile = useGravitreMobileViewport()
  const [viewMode, setViewMode] = useState<OverviewViewMode>("field")
  const [streamOpen, setStreamOpen] = useState(false)
  const [mobilePanel, setMobilePanel] = useState<MobilePanel>("main")
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [matrixCellKey, setMatrixCellKey] = useState<string | null>(null)
  const [matrixFocusIds, setMatrixFocusIds] = useState<string[]>([])

  const changeEvents = useMemo(() => buildChangeEvents(pageContext), [pageContext])
  const canonicalGraphNodes = useMemo(
    () => (pageContext?.graph?.nodes ?? undefined) as CanonicalGraphNode[] | undefined,
    [pageContext?.graph?.nodes],
  )

  const knownEntities = entityCount ?? pageContext?.metrics?.knowledge?.knownEntities ?? null
  const knownRels = relationshipCount ?? pageContext?.metrics?.knowledge?.knownRelationships ?? null
  const graphNodes = pageContext?.graph?.nodes?.length ?? 0
  const instanceNodes =
    pageContext?.graph?.nodes?.filter(
      (n) => n && typeof n === "object" && (n as { metadata?: { instance?: boolean } }).metadata?.instance,
    ).length ?? 0

  const { mapLoading, isError, isEmpty, isSparse, showMap } = resolveOverviewFieldState({
    snapshotLoadState,
    activeLens,
    knownEntities,
    knownRels,
    graphNodes,
  })

  const streamEvents = useMemo(() => {
    if (activeLens === "learns") return changeEvents.filter((e) => e.kind === "learned")
    if (activeLens === "predicts") return changeEvents.filter((e) => e.kind === "prediction")
    if (activeLens === "improves") return changeEvents.filter((e) => e.kind === "changed" || e.kind === "learned")
    if (activeLens === "acts") return changeEvents.filter((e) => e.kind === "changed")
    return changeEvents
  }, [changeEvents, activeLens])

  const streamVisible = isMobile ? mobilePanel === "changes" : streamOpen

  const mergedFocus = useMemo(() => {
    const fromEvent = streamEvents.find((e) => e.id === selectedEventId)?.focusNodeIds ?? []
    return [...new Set([...(focusNodeIds ?? []), ...fromEvent, ...matrixFocusIds])]
  }, [focusNodeIds, selectedEventId, streamEvents, matrixFocusIds])

  const toggleStream = () => {
    if (isMobile) {
      setMobilePanel((p) => (p === "changes" ? "main" : "changes"))
      return
    }
    setStreamOpen((v) => !v)
  }

  const openFieldFromMatrix = (lens: IntelligenceMapLens) => {
    setViewMode("field")
    onLensChange(lens)
    setMobilePanel("main")
  }

  return (
    <div className={cn("space-y-3", className)} data-testid="intelligence-i1-i2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-2.5">
          <NucleoIntelligence size={18} className="shrink-0 text-[color:var(--g-intelligence)]" />
          <div className="min-w-0">
            <p className="truncate text-[14px] font-semibold tracking-[-0.01em] text-foreground">
              {LENS_QUESTIONS[activeLens]}
            </p>
            <p className={cn(TYPE.meta, "tabular-nums")}>
              {viewMode === "matrix" ? "Matrix lens" : "Field topology"} ·{" "}
              {mapLoading
                ? "Loading…"
                : `${knownEntities ?? "—"} entities · ${knownRels ?? "—"} relationships · ${instanceNodes} on the map`}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <div
            className="inline-flex rounded-md border border-[color:var(--g-border-subtle)] p-0.5"
            role="group"
            aria-label="Intelligence view mode"
            data-testid="intel-view-mode"
          >
            <Button
              type="button"
              size="sm"
              variant={viewMode === "field" ? "secondary" : "ghost"}
              className="h-8"
              aria-pressed={viewMode === "field"}
              onClick={() => setViewMode("field")}
            >
              Field
            </Button>
            <Button
              type="button"
              size="sm"
              variant={viewMode === "matrix" ? "secondary" : "ghost"}
              className="h-8"
              aria-pressed={viewMode === "matrix"}
              onClick={() => setViewMode("matrix")}
            >
              Matrix
            </Button>
          </div>
          <Button
            type="button"
            size="sm"
            variant={streamVisible ? "secondary" : "outline"}
            data-testid="intel-i2-toggle"
            onClick={toggleStream}
          >
            {streamVisible ? "Hide changes" : "What changed?"}
          </Button>
        </div>
      </div>

      {isMobile ? (
        <div
          className="flex gap-1 rounded-md border border-[color:var(--g-border-subtle)] p-0.5"
          role="tablist"
          aria-label="Intelligence mobile panels"
          data-testid="intel-mobile-panels"
        >
          {(["main", "changes"] as const).map((panel) => (
            <button
              key={panel}
              type="button"
              role="tab"
              aria-selected={mobilePanel === panel}
              className={cn(
                "flex-1 rounded px-3 py-1.5 text-xs font-semibold capitalize",
                mobilePanel === panel
                  ? "bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]"
                  : "text-[color:var(--g-text-muted)]",
              )}
              onClick={() => setMobilePanel(panel)}
            >
              {panel === "main" ? (viewMode === "matrix" ? "Matrix" : "Graph") : "Changes"}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex gap-1 overflow-x-auto pb-1" role="tablist" aria-label="Intelligence map lenses">
        {INTELLIGENCE_MAP_LENSES.map((lens) => {
          const active = activeLens === lens.id
          const stat = lensMetrics[lens.id]
          return (
            <button
              key={lens.id}
              type="button"
              role="tab"
              aria-selected={active}
              title={lens.description}
              onClick={() => {
                onLensChange(lens.id)
                setSelectedEventId(null)
                setMatrixCellKey(null)
              }}
              className={cn(
                "shrink-0 rounded-md px-3 py-1.5 text-left transition-colors",
                active
                  ? "bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]"
                  : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              <span className="block text-xs font-semibold">{lens.label}</span>
              <span className={cn(TYPE.meta, "block tabular-nums")}>{stat.value}</span>
            </button>
          )
        })}
      </div>

      <div
        className={cn(
          "relative flex flex-1 gap-0 overflow-hidden rounded-[16px] bg-[color:var(--g-surface-1)] ring-1 ring-[color:var(--g-border-subtle)]",
          "min-h-[64vh]",
          isMobile && "flex-col",
        )}
      >
        {(!isMobile || mobilePanel === "changes") && (
          <IntelligenceChangeStream
            open={streamVisible}
            isMobile={isMobile}
            reducedMotion={reducedMotion ?? false}
            activeLens={activeLens}
            streamEvents={streamEvents}
            selectedEventId={selectedEventId}
            pageContext={pageContext}
            onSelectEvent={setSelectedEventId}
            onSelectionChange={onSelectionChange}
          />
        )}

        {(!isMobile || mobilePanel === "main") && (
          <div className="relative min-h-[64vh] min-w-0 flex-1">
            {mapLoading ? (
              <div
                className="relative z-30 flex min-h-[64vh] items-center justify-center rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]"
                aria-live="polite"
                aria-busy="true"
                data-testid="intel-field-loading"
              >
                <p className={TYPE.meta}>Loading intelligence field…</p>
              </div>
            ) : null}

            {isError ? (
              <div className="flex min-h-[64vh] flex-col items-center justify-center gap-3 p-6 text-center">
                <p className={TYPE.sectionTitle}>Unable to load intelligence</p>
                <p className={cn(TYPE.bodyMuted, "max-w-sm")}>
                  Page-context failed. Retry the same org-scoped contract — no invented graph.
                </p>
              </div>
            ) : null}

            {isEmpty || isSparse ? (
              <div
                className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[color:var(--g-surface-1)]/95 p-6 text-center"
                data-testid="intel-empty-sparse"
              >
                <p className={TYPE.sectionTitle}>
                  {isEmpty ? "No knowledge graph yet" : "No displayable field entities"}
                </p>
                <p className={cn(TYPE.bodyMuted, "mt-2 max-w-md")}>
                  {isEmpty
                    ? "Connect sources and sync your CRM to map how your entities relate."
                    : `${knownRels} relationships are recorded, but their entities can't be placed on the map yet.`}
                </p>
                <div className="mt-4 flex flex-wrap justify-center gap-2">
                  <Button type="button" size="sm" asChild>
                    <Link href={APP_ROUTES.connectors}>Open connectors</Link>
                  </Button>
                </div>
              </div>
            ) : null}

            {!mapLoading && !isError && !isEmpty && !isSparse && viewMode === "matrix" ? (
              <IntelligenceMatrixLens
                graphNodes={canonicalGraphNodes}
                selectedCellKey={matrixCellKey}
                onSelectCell={(key, lens, nodeIds) => {
                  setMatrixCellKey(key)
                  setMatrixFocusIds(nodeIds)
                  if (key) onLensChange(lens)
                }}
                onOpenFieldView={openFieldFromMatrix}
                className="min-h-[64vh] p-2"
              />
            ) : null}

            {showMap && viewMode === "field" ? (
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
                focusNodeIds={mergedFocus}
                cacheKey={cacheKey}
                className="min-h-[64vh]"
              />
            ) : null}
          </div>
        )}
      </div>

      <IntelligenceInspectorDrawer
        selection={selection}
        onSelectionChange={onSelectionChange}
        pageContext={pageContext}
        whyData={whyEvidence}
        onAskAbout={onAskAbout}
      />

      {selectedEventId && onAskAbout && isMobile && mobilePanel === "changes" ? (
        <div className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
          <p className={TYPE.eyebrow}>Ask · canonical workspace</p>
          <Button
            type="button"
            size="sm"
            className="mt-2"
            onClick={() => {
              const ev = streamEvents.find((e) => e.id === selectedEventId)
              if (ev) onAskAbout(ev.askPrompt)
            }}
          >
            Ask about change
          </Button>
        </div>
      ) : null}
    </div>
  )
}
