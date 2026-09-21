"use client"

/**
 * UX/UI 3.0 Plus — I1 Field Topology + contextual I2 Change Stream
 * Production surface for /intelligence OverviewLivingMap.
 * Uses canonical page-context graph + snapshot events — no fabricated telemetry.
 */

import { useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import Link from "next/link"
import type { IntelligencePageContextResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import { IntelligenceMap, type IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import { IntelligenceInspectorDrawer } from "@/components/intelligence/map/intelligence-inspector-drawer"
import type { IntelligenceLensMetrics } from "@/components/intelligence/map/intelligence-map-lens"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import { INTELLIGENCE_MAP_LENSES } from "@/components/intelligence/map/intelligence-map-lens"
import type { AllDepartmentsPayload } from "@/components/intelligence/why-gravitre-panel"
import type { SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { EvidenceChip } from "@/components/gravitre/creative-grammar"
import { Button } from "@/components/ui/button"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { buildChangeEvents } from "@/lib/intelligence/build-change-events"
import { resolveOverviewFieldState } from "@/lib/intelligence/overview-field-state"

const LENS_QUESTIONS: Record<IntelligenceMapLens, string> = {
  knows: "What does Gravitre know about this business?",
  learns: "What has Gravitre learned recently?",
  predicts: "What is Gravitre predicting?",
  acts: "What is Gravitre doing?",
  improves: "What has improved?",
}

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
  const [streamOpen, setStreamOpen] = useState(false)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const changeEvents = useMemo(() => buildChangeEvents(pageContext), [pageContext])

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

  const mergedFocus = useMemo(() => {
    const fromEvent = streamEvents.find((e) => e.id === selectedEventId)?.focusNodeIds ?? []
    return [...new Set([...(focusNodeIds ?? []), ...fromEvent])]
  }, [focusNodeIds, selectedEventId, streamEvents])

  return (
    <div className={cn("space-y-3", className)} data-testid="intelligence-i1-i2">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex min-w-0 items-start gap-2">
          <NucleoIntelligence size={22} className="mt-0.5 shrink-0" />
          <div>
            <p className={TYPE.eyebrow}>Intelligence · Field topology</p>
            <p className={cn(TYPE.meta, "mt-0.5 max-w-xl")}>{LENS_QUESTIONS[activeLens]}</p>
            <p className={cn(TYPE.meta, "mt-1 text-muted-foreground")}>
              {mapLoading
                ? "Loading…"
                : `${knownEntities ?? "—"} entities · ${knownRels ?? "—"} relationships · ${instanceNodes} displayable field nodes`}
            </p>
          </div>
        </div>
        <Button
          type="button"
          size="sm"
          variant={streamOpen ? "secondary" : "outline"}
          data-testid="intel-i2-toggle"
          onClick={() => setStreamOpen((v) => !v)}
        >
          {streamOpen ? "Hide changes" : "What changed?"}
        </Button>
      </div>

      {/* Lens tabs — emphasis on one graph; metrics are secondary, not the sole lens UX */}
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
              }}
              className={cn(
                "shrink-0 rounded-md px-3 py-1.5 text-left transition-colors",
                active
                  ? "bg-[color:var(--g-intelligence-soft)] text-[color:var(--g-intelligence)]"
                  : "text-[color:var(--g-text-muted)] hover:bg-[color:var(--g-surface-2)]",
              )}
            >
              <span className="block text-xs font-semibold uppercase tracking-wide">{lens.label}</span>
              <span className={cn(TYPE.meta, "block tabular-nums")}>{stat.value}</span>
            </button>
          )
        })}
      </div>

      <div className={cn("relative flex flex-1 gap-0", "min-h-[56vh]")}>
        <AnimatePresence>
          {streamOpen && !isEmpty && !isError ? (
            <motion.aside
              initial={reducedMotion ? false : { width: 0, opacity: 0 }}
              animate={{ width: 260, opacity: 1 }}
              exit={reducedMotion ? undefined : { width: 0, opacity: 0 }}
              className="hidden w-[260px] shrink-0 overflow-hidden border-r border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] md:block"
              data-testid="intel-i2-stream"
            >
              <p className={cn(TYPE.eyebrow, "px-3 pt-3")}>Change stream · I2</p>
              <p className={cn(TYPE.meta, "px-3 pb-2")}>Contextual · filtered by {activeLens}</p>
              <ul className="max-h-[52vh] overflow-y-auto px-2 pb-3">
                {streamEvents.length === 0 ? (
                  <li className={cn(TYPE.meta, "px-2 py-3")}>No change events in this lens window.</li>
                ) : (
                  streamEvents.map((ev) => (
                    <li key={ev.id}>
                      <button
                        type="button"
                        className={cn(
                          "w-full rounded-md px-2 py-2 text-left hover:bg-[color:var(--g-surface-2)]",
                          selectedEventId === ev.id && "bg-[color:var(--g-surface-2)]",
                        )}
                        onClick={() => {
                          setSelectedEventId(ev.id)
                          if (ev.focusNodeIds[0] && pageContext?.graph) {
                            const node = pageContext.graph.nodes.find((n) => n.id === ev.focusNodeIds[0])
                            if (node) {
                              onSelectionChange({
                                kind: "satellite",
                                node: {
                                  id: String(node.id),
                                  kind: "entity-type",
                                  label: String(node.businessLabel ?? node.id),
                                  sublabel: String(node.type ?? ""),
                                  emphasis: 1,
                                },
                              })
                            }
                          }
                        }}
                      >
                        <EvidenceChip label={ev.kind} tone="evidence" />
                        <p className="mt-1 text-xs font-semibold text-[color:var(--g-text-primary)]">{ev.title}</p>
                        {ev.at ? <p className={cn(TYPE.meta, "mt-0.5")}>{ev.at}</p> : null}
                      </button>
                    </li>
                  ))
                )}
              </ul>
            </motion.aside>
          ) : null}
        </AnimatePresence>

        <div className="relative min-h-[56vh] min-w-0 flex-1">
          {mapLoading ? (
            <div
              className="relative z-30 flex min-h-[56vh] items-center justify-center rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]"
              aria-live="polite"
              aria-busy="true"
              data-testid="intel-field-loading"
            >
              <p className={TYPE.meta}>Loading intelligence field…</p>
            </div>
          ) : null}

          {isError ? (
            <div className="flex min-h-[56vh] flex-col items-center justify-center gap-3 p-6 text-center">
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
                  ? "Connect sources and sync CRM so org_entity_relationships can resolve entity ids."
                  : `${knownRels} relationship rows are counted, but endpoint entity ids are not displayable as field nodes. Do not invent nodes.`}
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <Button type="button" size="sm" asChild>
                  <Link href={APP_ROUTES.connectors}>Open connectors</Link>
                </Button>
              </div>
            </div>
          ) : null}

          {showMap ? (
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
              className="min-h-[56vh]"
            />
          ) : null}
        </div>
      </div>

      <IntelligenceInspectorDrawer
        selection={selection}
        onSelectionChange={onSelectionChange}
        pageContext={pageContext}
        whyData={whyEvidence}
        onAskAbout={onAskAbout}
      />

      {selectedEventId && onAskAbout ? (
        <div className="rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3 md:hidden">
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
