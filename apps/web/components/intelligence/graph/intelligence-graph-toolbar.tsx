"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { MapNodeKind } from "@/components/intelligence/map/map-topology"
import { cn } from "@/lib/utils"
import {
  Crosshair,
  Filter,
  List,
  Maximize2,
  Minimize2,
  RotateCcw,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react"

const NODE_KINDS: Array<{ id: MapNodeKind; label: string }> = [
  { id: "department", label: "Departments" },
  { id: "agent", label: "Agents" },
  { id: "entity-type", label: "Entities" },
  { id: "model", label: "Models" },
  { id: "signal", label: "Signals" },
  { id: "learning", label: "Learning" },
]

export function IntelligenceGraphToolbar({
  searchQuery,
  onSearchChange,
  kindFilter,
  onKindFilterChange,
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
  onFocusSelected,
  isFullscreen,
  onToggleFullscreen,
  hasSelection,
  className,
  spatialEnabled,
  onSpatialChange,
  spatialDisabled,
  listView,
  onListViewChange,
}: {
  searchQuery: string
  onSearchChange: (value: string) => void
  kindFilter: Set<MapNodeKind> | null
  onKindFilterChange: (kinds: Set<MapNodeKind> | null) => void
  onZoomIn: () => void
  onZoomOut: () => void
  onFit: () => void
  onReset: () => void
  onFocusSelected: () => void
  isFullscreen: boolean
  onToggleFullscreen: () => void
  hasSelection: boolean
  className?: string
  spatialEnabled?: boolean
  onSpatialChange?: (enabled: boolean) => void
  spatialDisabled?: boolean
  listView?: boolean
  onListViewChange?: (enabled: boolean) => void
}) {
  const activeKinds = kindFilter ?? new Set(NODE_KINDS.map((k) => k.id))

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-[var(--np-radius-md)] border border-divide/80 bg-[color:var(--g-surface-1)]/90 p-1.5 backdrop-blur-sm",
        className,
      )}
      role="toolbar"
      aria-label="Graph controls"
    >
      <div className="relative min-w-[10rem] flex-1 sm:max-w-xs">
        <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search nodes…"
          className="h-8 pl-8 text-xs"
          aria-label="Search graph nodes"
        />
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs">
            <Filter className="h-3.5 w-3.5" />
            Filter
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          {NODE_KINDS.map((kind) => (
            <DropdownMenuCheckboxItem
              key={kind.id}
              checked={activeKinds.has(kind.id)}
              onCheckedChange={(checked) => {
                const next = new Set(activeKinds)
                if (checked) next.add(kind.id)
                else next.delete(kind.id)
                onKindFilterChange(next.size === NODE_KINDS.length ? null : next)
              }}
            >
              {kind.label}
            </DropdownMenuCheckboxItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="flex items-center gap-0.5">
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomIn} aria-label="Zoom in">
          <ZoomIn className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onZoomOut} aria-label="Zoom out">
          <ZoomOut className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onFit} aria-label="Fit to view">
          <Maximize2 className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onReset} aria-label="Reset layout">
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onFocusSelected}
          disabled={!hasSelection}
          aria-label="Focus selected node"
        >
          <Crosshair className="h-4 w-4" />
        </Button>
        <Button
          variant={listView ? "secondary" : "ghost"}
          size="sm"
          className="h-8 text-xs"
          aria-pressed={Boolean(listView)}
          onClick={() => onListViewChange?.(!listView)}
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
        >
          Spatial
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={onToggleFullscreen}
          aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen graph"}
        >
          {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
        </Button>
      </div>
    </div>
  )
}
