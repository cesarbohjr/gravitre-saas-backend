"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"
import { MAP_KIND_NUCLEO } from "@/components/intelligence/graph/nodus-graph-node"
import { cn } from "@/lib/utils"
import {
  Crosshair,
  List,
  Maximize,
  Minimize,
  Minus,
  Plus,
  RotateCcw,
  Scan,
  Search,
} from "lucide-react"

/**
 * Node kinds double as the legend and the filter, the way cluster and
 * embedding explorers (TensorBoard Projector, Plotly legends) let you click a
 * category to show or hide it. Each chip shows the same icon its nodes use.
 */
export const GRAPH_NODE_KINDS: Array<{ id: MapNodeKind; label: string }> = [
  { id: "department", label: "Departments" },
  { id: "agent", label: "Agents" },
  { id: "entity-type", label: "Entities" },
  { id: "model", label: "Models" },
  { id: "signal", label: "Forecasts" },
  { id: "learning", label: "Learnings" },
]

export function IntelligenceGraphToolbar({
  searchQuery,
  onSearchChange,
  searchMatchCount,
  kindFilter,
  onKindFilterChange,
  kindCounts,
  isFullscreen,
  onToggleFullscreen,
  className,
  spatialEnabled,
  onSpatialChange,
  spatialDisabled,
  listView,
  onListViewChange,
}: {
  searchQuery: string
  onSearchChange: (value: string) => void
  searchMatchCount?: number
  kindFilter: Set<MapNodeKind> | null
  onKindFilterChange: (kinds: Set<MapNodeKind> | null) => void
  /** Nodes per kind in the current lens; kinds with no nodes are not offered. */
  kindCounts: Partial<Record<MapNodeKind, number>>
  isFullscreen: boolean
  onToggleFullscreen: () => void
  className?: string
  spatialEnabled?: boolean
  onSpatialChange?: (enabled: boolean) => void
  spatialDisabled?: boolean
  listView?: boolean
  onListViewChange?: (enabled: boolean) => void
}) {
  const present = GRAPH_NODE_KINDS.filter((k) => (kindCounts[k.id] ?? 0) > 0)
  const activeKinds = kindFilter ?? new Set(GRAPH_NODE_KINDS.map((k) => k.id))

  const toggleKind = (kind: MapNodeKind) => {
    const next = new Set(activeKinds)
    if (next.has(kind)) next.delete(kind)
    else next.add(kind)
    onKindFilterChange(next.size === GRAPH_NODE_KINDS.length ? null : next)
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-2 rounded-[var(--np-radius-md)] border border-divide/80 bg-[color:var(--g-surface-1)]/90 p-1.5 backdrop-blur-sm",
        className,
      )}
      role="toolbar"
      aria-label="Graph controls"
    >
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[10rem] flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Find a node…"
            className="h-8 pl-8 text-xs"
            aria-label="Search graph nodes"
          />
          {searchQuery.trim() && searchMatchCount != null ? (
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] tabular-nums text-muted-foreground">
              {searchMatchCount} found
            </span>
          ) : null}
        </div>

        <div className="ml-auto flex items-center gap-1">
          <Button
            variant={listView ? "secondary" : "ghost"}
            size="sm"
            className="h-8 text-xs"
            aria-pressed={Boolean(listView)}
            onClick={() => onListViewChange?.(!listView)}
            title="Show the same nodes as an accessible list"
          >
            <List className="mr-1 h-3.5 w-3.5" />
            List
          </Button>
          <Button
            variant={spatialEnabled ? "secondary" : "ghost"}
            size="sm"
            className="h-8 text-xs"
            aria-pressed={Boolean(spatialEnabled)}
            disabled={spatialDisabled}
            onClick={() => onSpatialChange?.(!spatialEnabled)}
            title="Add depth so dense areas spread out"
          >
            Depth
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onToggleFullscreen}
            aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen graph"}
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      {present.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 px-0.5" role="group" aria-label="Show node types">
          <span className="mr-1 text-[11px] font-medium text-muted-foreground">Show</span>
          {present.map((kind) => {
            const on = activeKinds.has(kind.id)
            const Icon = MAP_KIND_NUCLEO[kind.id]
            return (
              <button
                key={kind.id}
                type="button"
                aria-pressed={on}
                onClick={() => toggleKind(kind.id)}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  on
                    ? "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-2)] text-foreground"
                    : "border-dashed border-[color:var(--g-border-subtle)] text-muted-foreground line-through decoration-1",
                )}
              >
                <Icon size={12} aria-hidden className={on ? "text-[color:var(--g-brand)]" : "opacity-50"} />
                {kind.label}
                <span className="tabular-nums text-muted-foreground">{kindCounts[kind.id]}</span>
              </button>
            )
          })}
          {kindFilter ? (
            <button
              type="button"
              className="ml-1 text-[11px] font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]"
              onClick={() => onKindFilterChange(null)}
            >
              Show all
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

/**
 * Map-style view controls pinned to the canvas corner: zoom steps with the
 * current level, fit everything, focus the selection, and reset the layout.
 */
export function IntelligenceGraphViewControls({
  scale,
  onZoomIn,
  onZoomOut,
  onFit,
  onFocusSelected,
  onReset,
  hasSelection,
  canZoomIn,
  canZoomOut,
}: {
  scale: number
  onZoomIn: () => void
  onZoomOut: () => void
  onFit: () => void
  onFocusSelected: () => void
  onReset: () => void
  hasSelection: boolean
  canZoomIn: boolean
  canZoomOut: boolean
}) {
  const button =
    "flex h-8 w-8 items-center justify-center text-[color:var(--g-text-secondary)] transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)] disabled:pointer-events-none disabled:opacity-40"
  return (
    <div
      className="absolute bottom-3 right-3 z-30 flex flex-col items-end gap-2"
      onPointerDown={(e) => e.stopPropagation()}
      data-testid="intelligence-graph-view-controls"
    >
      <div className="flex flex-col overflow-hidden rounded-md border border-border bg-[color:var(--g-surface-1)]/95 shadow-sm">
        <button type="button" className={button} onClick={onZoomIn} disabled={!canZoomIn} aria-label="Zoom in" title="Zoom in (+)">
          <Plus className="h-4 w-4" />
        </button>
        <span
          className="flex h-6 w-8 items-center justify-center border-y border-border text-[10px] font-medium tabular-nums text-muted-foreground"
          aria-live="polite"
          aria-label={`Zoom ${Math.round(scale * 100)} percent`}
        >
          {Math.round(scale * 100)}%
        </span>
        <button type="button" className={button} onClick={onZoomOut} disabled={!canZoomOut} aria-label="Zoom out" title="Zoom out (−)">
          <Minus className="h-4 w-4" />
        </button>
      </div>
      <div className="flex flex-col overflow-hidden rounded-md border border-border bg-[color:var(--g-surface-1)]/95 shadow-sm">
        <button type="button" className={button} onClick={onFit} aria-label="Fit to view" title="Fit everything (0)">
          <Scan className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={cn(button, "border-t border-border")}
          onClick={onFocusSelected}
          disabled={!hasSelection}
          aria-label="Focus selected node"
          title="Focus selected node"
        >
          <Crosshair className="h-4 w-4" />
        </button>
        <button
          type="button"
          className={cn(button, "border-t border-border")}
          onClick={onReset}
          aria-label="Reset layout"
          title="Reset layout and zoom"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
