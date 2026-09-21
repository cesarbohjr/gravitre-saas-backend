"use client"

/**
 * I2 — Intelligence graph stage: composes IntelligenceGraph → LayoutEngine →
 * InteractionController → DomSvgRenderer. Product rendering layer (I3 extends polish).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import type { IntelligenceCoreStateResponse } from "@/lib/api"
import type { Agent } from "@/types/api"
import { CoreHubNode } from "@/components/intelligence/core/core-hub-node"
import { DepartmentNode } from "@/components/intelligence/core/department-node"
import { SignalEdge } from "@/components/intelligence/core/signal-edge"
import { ConnectorsAtmosphere } from "@/components/gravitre/connectors-atmosphere"
import { MapSatelliteNode } from "@/components/intelligence/map/map-satellite-node"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  CORE_ID,
  signalDepartmentKey,
  type MapNode,
} from "@/components/intelligence/map/map-topology"
import { IntelligenceGraphToolbar } from "@/components/intelligence/graph/intelligence-graph-toolbar"
import { IntelligenceGraphList } from "@/components/intelligence/graph/intelligence-graph-list"
import {
  DomSvgGraphRenderer,
  IntelligenceGraph,
  SpatialGraphRenderer,
  useGraphInteraction,
  DEFAULT_VIEWBOX,
  CLUSTER_THRESHOLD,
  isDenseGraph,
  shouldShowNodeLabel,
  type GraphPoint,
} from "@/lib/intelligence/graph"
import {
  focusedRelationshipPaths,
  isCompactIntelligenceViewport,
} from "@/lib/intelligence/mobile-relationship-paths"
import { useIntelligenceCoreState } from "@/lib/intelligence/use-core-state"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { cn } from "@/lib/utils"
import { Warning } from "@phosphor-icons/react"

const VB = DEFAULT_VIEWBOX
const CENTER = { cx: VB.w / 2, cy: VB.h / 2 }
const domRenderer = new DomSvgGraphRenderer()
const spatialRenderer = new SpatialGraphRenderer()

type BusinessSignalRow = Record<string, unknown>

export type IntelligenceMapSelection =
  | { kind: "department"; department: import("@/lib/api").IntelligenceCoreDepartment }
  | { kind: "agent"; agent: Agent }
  | { kind: "signal"; signal: BusinessSignalRow }
  | { kind: "satellite"; node: MapNode }
  | { kind: "edge"; edgeId: string; label: string }
  | null

function selectionKey(selection: IntelligenceMapSelection): string | null {
  if (!selection) return null
  if (selection.kind === "edge") return `edge:${selection.edgeId}`
  if (selection.kind === "department") return `dept:${selection.department.id}`
  if (selection.kind === "agent") return `agent:${selection.agent.id}`
  if (selection.kind === "signal") {
    return `signal:${readString(selection.signal.id, readString(selection.signal.title, ""))}`
  }
  return selection.node.id
}

function CoreStats({
  data,
  lens,
  entityCount,
  relationshipCount,
}: {
  data: IntelligenceCoreStateResponse
  lens: IntelligenceMapLens
  entityCount?: number | null
  relationshipCount?: number | null
  caption?: string
}) {
  const lines: string[] = []
  if (lens === "knows") {
    if (entityCount != null) lines.push(`${entityCount.toLocaleString()} entities`)
    if (relationshipCount != null) lines.push(`${relationshipCount.toLocaleString()} relationships`)
  } else if (lens === "acts") {
    if (data.core.activeAgentRuns > 0) {
      lines.push(`${data.core.activeAgentRuns} agent run${data.core.activeAgentRuns === 1 ? "" : "s"}`)
    }
  }
  // Never paint a center watermark / repeated caption — caption already lives top-left.
  if (lines.length === 0) return null
  return (
    <div className="pointer-events-none absolute left-1/2 top-[calc(50%+4.75rem)] z-20 max-w-xs -translate-x-1/2 px-4 text-center">
      <p className="text-xs font-medium text-[color:var(--g-text-secondary)]">{lines.join(" · ")}</p>
    </div>
  )
}

export function IntelligenceGraphStage({
  lens,
  canonicalGraph,
  signals,
  agents,
  entityTypes,
  readiness,
  orgTraining,
  entityCount,
  relationshipCount,
  selection,
  onSelectionChange,
  highlightNodeIds,
  dimNodeIds,
  focusNodeIds,
  className,
  cacheKey,
}: {
  lens: IntelligenceMapLens
  canonicalGraph?: { nodes: Record<string, unknown>[]; edges: Record<string, unknown>[] } | null
  signals?: BusinessSignalRow[] | null
  agents?: Agent[] | null
  entityTypes?: string[] | null
  readiness?: Record<string, unknown> | null
  orgTraining?: Record<string, { artifact_loaded?: boolean }> | null
  entityCount?: number | null
  relationshipCount?: number | null
  selection?: IntelligenceMapSelection
  onSelectionChange?: (selection: IntelligenceMapSelection) => void
  highlightNodeIds?: string[]
  dimNodeIds?: string[]
  focusNodeIds?: string[]
  className?: string
  cacheKey?: string
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [spatialEnabled, setSpatialEnabled] = useState(false)
  const [compactViewport, setCompactViewport] = useState(false)
  const [mobileExplorerOpen, setMobileExplorerOpen] = useState(false)
  const [listView, setListView] = useState(false)
  const [dragPositions, setDragPositions] = useState<Map<string, GraphPoint>>(new Map())
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  useEffect(() => {
    const update = () => setCompactViewport(isCompactIntelligenceViewport())
    update()
    window.addEventListener("resize", update)
    return () => window.removeEventListener("resize", update)
  }, [])

  const { data, error, isLoading } = useIntelligenceCoreState(true, 24)
  const interaction = useGraphInteraction()

  const graph = useMemo(
    () =>
      new IntelligenceGraph({
        lens,
        canonicalGraph,
        agents,
        entityTypes,
        readiness,
        orgTraining,
        signals,
        coreState: data ?? null,
      }),
    [lens, canonicalGraph, agents, entityTypes, readiness, orgTraining, signals, data],
  )

  const layoutCacheKey = cacheKey ?? `org:${lens}`

  const pinnedPositions = useMemo(() => {
    const merged = new Map(interaction.state.pinnedPositions)
    dragPositions.forEach((pos, id) => merged.set(id, pos))
    return merged
  }, [interaction.state.pinnedPositions, dragPositions])

  const renderModel = useMemo(
    () =>
      graph.buildRenderModel({
        cacheKey: layoutCacheKey,
        pinnedPositions,
        collapsedClusterIds: interaction.state.collapsedClusterIds,
        expandedClusterIds: interaction.state.expandedClusterIds,
      }),
    [graph, layoutCacheKey, pinnedPositions, interaction.state.collapsedClusterIds, interaction.state.expandedClusterIds],
  )

  const searchMatches = useMemo(() => {
    if (!interaction.state.searchQuery.trim()) return new Set<string>()
    return new Set(graph.searchNodes(interaction.state.searchQuery).map((n) => n.id))
  }, [graph, interaction.state.searchQuery])

  const highlightSet = useMemo(() => {
    const set = new Set(highlightNodeIds ?? [])
    searchMatches.forEach((id) => set.add(id))
    return set
  }, [highlightNodeIds, searchMatches])

  const dimSet = useMemo(() => new Set(dimNodeIds ?? []), [dimNodeIds])

  const payload = useMemo(() => {
    const renderer = spatialEnabled && !reduced ? spatialRenderer : domRenderer
    return renderer.prepare({
      model: renderModel,
      viewport: interaction.state.viewport,
      selectedNodeId: selectionKey(selection ?? null),
      hoveredNodeId: null,
      hoveredEdgeId: null,
      highlightNodeIds: highlightSet,
      dimNodeIds: dimSet,
      searchMatchIds: searchMatches,
      pathHighlightIds: highlightSet,
      kindFilter: interaction.state.kindFilter,
      reducedMotion: reduced,
    })
  }, [
    renderModel,
    interaction.state.kindFilter,
    selection,
    highlightSet,
    dimSet,
    searchMatches,
    reduced,
    spatialEnabled,
  ])

  const densePan = isDenseGraph(graph.nodes.length) || graph.nodes.length >= CLUSTER_THRESHOLD
  const viewport = interaction.state.viewport
  const selectedId = selectionKey(selection ?? null)

  const toggleSelection = useCallback(
    (node: MapNode) => {
      const isSelected = selectedId === node.id
      if (isSelected) {
        onSelectionChange?.(null)
        interaction.setSelectedNodeId(null)
        return
      }
      interaction.setSelectedNodeId(node.id)
      if (node.kind === "department" && node.department) {
        onSelectionChange?.({ kind: "department", department: node.department })
        return
      }
      if (node.kind === "agent" && node.agent) {
        onSelectionChange?.({ kind: "agent", agent: node.agent })
        return
      }
      if (node.kind === "signal" && node.signal) {
        onSelectionChange?.({ kind: "signal", signal: node.signal })
        return
      }
      onSelectionChange?.({ kind: "satellite", node })
    },
    [selectedId, onSelectionChange, interaction],
  )

  useEffect(() => {
    if (!focusNodeIds?.length) return
    interaction.fitToView(renderModel.layout.positions, focusNodeIds)
  }, [focusNodeIds, renderModel.layout.positions, interaction])

  useEffect(() => {
    const onFullscreenChange = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener("fullscreenchange", onFullscreenChange)
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange)
  }, [])

  const warningsByDept = useMemo(() => {
    const map = new Map<string, BusinessSignalRow>()
    for (const signal of signals ?? []) {
      const key = signalDepartmentKey(signal)
      if (key && !map.has(key)) map.set(key, signal)
    }
    return map
  }, [signals])

  const visibleNodeIds = useMemo(
    () => payload.nodes.filter((n) => !n.hidden).map((n) => n.id),
    [payload.nodes],
  )

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault()
        interaction.cycleKeyboardFocus(visibleNodeIds, 1)
      } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault()
        interaction.cycleKeyboardFocus(visibleNodeIds, -1)
      } else if (event.key === "Enter" && interaction.state.selectedNodeId) {
        const node = graph.nodeById(interaction.state.selectedNodeId)
        if (node) toggleSelection(node)
      } else if (event.key === "Escape") {
        onSelectionChange?.(null)
        interaction.setSelectedNodeId(null)
      }
    },
    [interaction, visibleNodeIds, graph, toggleSelection, onSelectionChange],
  )

  const onNodeDrag = useCallback(
    (nodeId: string, point: GraphPoint) => {
      setDragPositions((prev) => {
        const next = new Map(prev)
        next.set(nodeId, point)
        return next
      })
    },
    [],
  )

  const hasNodes = graph.nodes.length > 0
  const mobilePaths = useMemo(() => focusedRelationshipPaths(graph.topology), [graph.topology])
  const showCompactPaths = compactViewport && !mobileExplorerOpen && !isFullscreen && !listView
  const showCanvas = !showCompactPaths && !listView

  return (
    <div className={cn("space-y-2", className)}>
      {showCompactPaths ? null : (
      <IntelligenceGraphToolbar
        searchQuery={interaction.state.searchQuery}
        onSearchChange={interaction.setSearchQuery}
        kindFilter={interaction.state.kindFilter}
        onKindFilterChange={interaction.setKindFilter}
        onZoomIn={interaction.zoomIn}
        onZoomOut={interaction.zoomOut}
        onFit={() => interaction.fitToView(renderModel.layout.positions)}
        onReset={() => {
          interaction.resetViewport()
          setDragPositions(new Map())
        }}
        onFocusSelected={() => {
          if (selectedId) interaction.focusNode(renderModel.layout.positions, selectedId)
        }}
        isFullscreen={isFullscreen}
        onToggleFullscreen={() => {
          const el = containerRef.current
          if (!el) return
          if (document.fullscreenElement) void document.exitFullscreen()
          else void el.requestFullscreen()
        }}
        hasSelection={Boolean(selectedId)}
        spatialEnabled={spatialEnabled && !reduced}
        onSpatialChange={setSpatialEnabled}
        spatialDisabled={reduced}
        listView={listView}
        onListViewChange={setListView}
      />
      )}

      <div className="sr-only" role="status" aria-live="polite">
        {selectedId
          ? `Selected ${graph.nodeById(selectedId)?.label ?? selectedId}`
          : "No graph node selected"}
      </div>

      {listView ? (
        <IntelligenceGraphList
          topology={graph.topology}
          selectedId={selectedId}
          onSelect={(nodeId) => {
            const node = graph.nodeById(nodeId)
            if (node) toggleSelection(node)
          }}
        />
      ) : null}

      {showCompactPaths ? (
        <div
          className="space-y-3 rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3 md:hidden"
          data-testid="intelligence-mobile-paths"
        >
          <p className={TYPE.eyebrow}>Relationship paths</p>
          <p className={cn(TYPE.meta, "text-pretty")}>
            On phones Gravitre shows focused paths and Ask Gravitre — not a shrunk 40-node canvas.
          </p>
          {mobilePaths.length === 0 ? (
            <p className="text-sm text-muted-foreground">No relationship paths in this lens yet.</p>
          ) : (
            <ul className="space-y-2">
              {mobilePaths.map((path) => (
                <li key={path.id} className="rounded-md border border-divide px-3 py-2 text-sm">
                  <span className="font-medium">{path.fromLabel}</span>
                  <span className="text-muted-foreground"> → {path.toLabel}</span>
                  <span className={cn(TYPE.meta, "mt-0.5 block")}>{path.edgeType}</span>
                </li>
              ))}
            </ul>
          )}
          <button
            type="button"
            className="text-sm font-medium text-[color:var(--g-brand)] hover:underline"
            onClick={() => setMobileExplorerOpen(true)}
          >
            Expand graph explorer
          </button>
        </div>
      ) : null}

      {compactViewport && mobileExplorerOpen ? (
        <button
          type="button"
          className="text-sm font-medium text-[color:var(--g-brand)] hover:underline md:hidden"
          onClick={() => setMobileExplorerOpen(false)}
        >
          Back to relationship paths
        </button>
      ) : null}

      <div
        ref={containerRef}
        id="intelligence-map-canvas"
        data-testid="intelligence-map-canvas"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        onWheel={interaction.handleWheel}
        onPointerDown={(e) => {
          if (e.target === e.currentTarget || (e.target as HTMLElement).dataset.panSurface === "true") {
            interaction.beginPan(e.clientX, e.clientY)
          }
        }}
        onPointerMove={(e) => {
          if (e.buttons === 0) return
          interaction.moveDrag(e.clientX, e.clientY, interaction.state.viewport.scale, onNodeDrag)
        }}
        onPointerUp={interaction.endDrag}
        onPointerLeave={interaction.endDrag}
        className={cn(
          "relative min-h-[44vh] flex-1 overflow-hidden rounded-[var(--np-radius-lg)] border border-divide bg-white shadow-[var(--np-shadow)] outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]",
          isFullscreen && "min-h-[100vh] rounded-none border-0",
          !showCanvas && "hidden",
        )}
        role="application"
        aria-label={`Interactive Gravitre intelligence map — ${lens} lens`}
      >
        <div data-pan-surface="true" className="absolute inset-0 z-0">
          <ConnectorsAtmosphere />
        </div>

        <p className={cn(TYPE.meta, "absolute left-3 top-2 z-20 max-w-[70%] truncate opacity-80")}>
          {graph.caption}
        </p>

        {error ? (
          <div className="relative z-10 flex h-full min-h-[44vh] items-center justify-center p-6 text-center">
            <p className={TYPE.cardTitle}>Unable to load live intelligence map</p>
          </div>
        ) : isLoading && !data && !canonicalGraph?.nodes?.length ? (
          <div className="relative z-10 flex h-full min-h-[44vh] items-center justify-center">
            <span className={TYPE.bodyMuted}>Loading live intelligence topology…</span>
          </div>
        ) : !hasNodes ? (
          <div className="relative z-10 flex h-full min-h-[44vh] flex-col items-center justify-center p-6 text-center">
            <CoreHubNode state={data?.core.state ?? "idle"} reduced={reduced} />
            <p className={cn(TYPE.cardTitle, "mt-4")}>{graph.caption || "No nodes in this lens yet"}</p>
          </div>
        ) : (
          <motion.div
            data-pan-surface="true"
            className="relative z-10 h-full min-h-[44vh] w-full origin-center cursor-grab active:cursor-grabbing"
            style={{
              aspectRatio: `${VB.w} / ${VB.h}`,
              willChange: "transform",
              ...(densePan
                ? {
                    transform: `translate(${viewport.translateX}%, ${viewport.translateY}%) scale(${viewport.scale})`,
                    transition: "none",
                  }
                : undefined),
            }}
            animate={
              densePan
                ? undefined
                : {
                    scale: viewport.scale,
                    x: `${viewport.translateX}%`,
                    y: `${viewport.translateY}%`,
                  }
            }
            transition={
              densePan || reduced ? { duration: 0 } : { type: "spring", stiffness: 140, damping: 22 }
            }
          >
            <svg
              viewBox={`0 0 ${VB.w} ${VB.h}`}
              className="absolute inset-0 h-full w-full"
              aria-hidden
              preserveAspectRatio="xMidYMid meet"
            >
              {payload.edges.map((edge) => {
                if (edge.hidden) return null
                const isHovered = false
                const isHighlighted =
                  highlightSet.has(edge.fromId === CORE_ID ? edge.toId : edge.fromId) ||
                  highlightSet.has(edge.toId)
                return (
                  <g
                    key={edge.id}
                    opacity={edge.hidden ? 0 : Math.min(1, edge.opacity * (edge.emphasis ?? 1))}
                    className="cursor-pointer hover:opacity-90"
                    onClick={(e) => {
                      e.stopPropagation()
                      onSelectionChange?.({
                        kind: "edge",
                        edgeId: edge.id,
                        label: edge.edgeType ?? edge.id,
                      })
                    }}
                  >
                    <SignalEdge
                      x1={edge.from.x}
                      y1={edge.from.y}
                      x2={edge.to.x}
                      y2={edge.to.y}
                      state={edge.state}
                      reduced={reduced}
                    />
                    {(isHovered || isHighlighted) && !reduced ? (
                      <circle cx={edge.to.x} cy={edge.to.y} r={4} fill="var(--g-brand)" opacity={0.5} />
                    ) : null}
                  </g>
                )
              })}
            </svg>

            <div
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${(payload.corePosition.x / VB.w) * 100}%`,
                top: `${(payload.corePosition.y / VB.h) * 100}%`,
              }}
            >
              <CoreHubNode state={data?.core.state ?? "idle"} reduced={reduced} />
            </div>

            {data ? (
              <CoreStats
                data={data}
                lens={lens}
                entityCount={entityCount}
                relationshipCount={relationshipCount}
              />
            ) : null}

            <AnimatePresence mode="popLayout">
              {payload.nodes.map((node) => {
                if (node.hidden) return null
                const isSelected = selectedId === node.id
                const isHighlighted = highlightSet.has(node.id)
                const isDimmed = dimSet.has(node.id) && !isHighlighted
                const isPinned = interaction.state.pinnedNodeIds.has(node.id)
                const showLabel = shouldShowNodeLabel({
                  scale: viewport.scale,
                  dense: densePan,
                  selected: isSelected,
                  highlighted: isHighlighted,
                })
                const warning =
                  node.kind === "department" && node.department
                    ? warningsByDept.get(node.department.id.toLowerCase())
                    : null

                return (
                  <motion.div
                    key={node.id}
                    layout={!reduced}
                    initial={reduced ? false : { opacity: 0, scale: 0.88 }}
                    animate={{
                      opacity: isDimmed ? 0.35 : 1,
                      scale: isDimmed ? 0.92 : 1,
                      left: `${(node.x / VB.w) * 100}%`,
                      top: `${(node.y / VB.h) * 100}%`,
                    }}
                    exit={reduced ? undefined : { opacity: 0, scale: 0.88 }}
                    transition={{ type: "spring", stiffness: 170, damping: 22 }}
                    className="absolute -translate-x-1/2 -translate-y-1/2 hover:z-10"
                  >
                    <button
                      type="button"
                      className={cn(
                        "relative rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)] hover:ring-2 hover:ring-[color:var(--g-brand)]/50",
                        isHighlighted && "ring-2 ring-[color:var(--g-brand)]",
                        isPinned && "ring-1 ring-amber-500/60",
                        isDimmed && "grayscale",
                      )}
                      onClick={() => toggleSelection(node)}
                      onPointerDown={(e) => {
                        e.stopPropagation()
                        interaction.beginNodeDrag(node.id, e.clientX, e.clientY, { x: node.x, y: node.y })
                      }}
                      onDoubleClick={(e) => {
                        e.stopPropagation()
                        interaction.focusNode(renderModel.layout.positions, node.id)
                        interaction.togglePin(node.id, { x: node.x, y: node.y })
                      }}
                      aria-label={`${node.label} ${node.kind} node${isPinned ? ", pinned" : ""}`}
                    >
                      {node.kind === "department" && node.department ? (
                        <DepartmentNode department={node.department} reduced={reduced} embedded />
                      ) : (
                        <MapSatelliteNode
                          node={node}
                          reduced={reduced}
                          selected={isSelected}
                          showLabel={showLabel}
                        />
                      )}
                    </button>
                    {warning && lens === "predicts" ? (
                      <button
                        type="button"
                        className="absolute -right-1 -top-1 z-30 flex h-6 w-6 items-center justify-center rounded-full border border-amber-500/50 bg-amber-50 text-amber-700"
                        onClick={(event) => {
                          event.stopPropagation()
                          onSelectionChange?.({ kind: "signal", signal: warning })
                        }}
                        aria-label={`Warning: ${readString(warning.title, "signal")}`}
                      >
                        <Warning className="h-3.5 w-3.5" weight="fill" />
                      </button>
                    ) : null}
                  </motion.div>
                )
              })}
            </AnimatePresence>

            {renderModel.layout.clusters.length > 0 ? (
              <div className="absolute bottom-3 left-3 z-30 flex flex-wrap gap-1">
                {renderModel.layout.clusters.map((cluster) => (
                  <button
                    key={cluster.id}
                    type="button"
                    data-testid="intelligence-graph-cluster"
                    aria-expanded={!cluster.collapsed}
                    className="rounded-full border border-divide bg-[color:var(--g-surface-1)]/90 px-2 py-0.5 text-[10px] font-medium"
                    onClick={() => interaction.toggleCluster(cluster.id)}
                  >
                    {cluster.collapsed ? `Expand ${cluster.label}` : `Collapse ${cluster.label}`}
                  </button>
                ))}
              </div>
            ) : null}
          </motion.div>
        )}
      </div>
    </div>
  )
}

/** Backward-compatible alias for Overview and tests. */
export const IntelligenceMap = IntelligenceGraphStage
