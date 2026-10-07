"use client"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { RELATIONSHIPS_SMOKE_DATA, relationshipTypeLabel } from "@/lib/learning-ui-copy"
import type { SortKey, ViewMode } from "@/lib/relationships-graph/types"
import { Graph, Plus, SlidersHorizontal, Table } from "@phosphor-icons/react"
import { NucleoSearch } from "@/components/icons/nucleo/semantic"
import { NUCLEO_SIZE } from "@/lib/design-system"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

export function RelationshipToolbar({
  workspace,
  hideAddEntity = false,
}: {
  workspace: RelationshipsWorkspaceState
  hideAddEntity?: boolean
}) {
  const {
    query,
    setQuery,
    setPage,
    typeFilter,
    setTypeFilter,
    sortKey,
    setSortKey,
    showArchived,
    setShowArchived,
    viewMode,
    setViewMode,
    viewControlled,
    relationshipTypes,
    openAddNode,
    showTestData,
    setShowTestData,
    perspective,
    setPerspective,
    selection,
    neighborhoodOn,
    setNeighborhoodOn,
    pinnedIds,
    togglePin,
    labelFor,
    nodes,
  } = workspace

  const filterCount = (showArchived ? 1 : 0) + (showTestData ? 1 : 0)

  return (
    <div className="flex flex-col gap-3">
      {viewControlled ? null : (
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={viewMode}
          onValueChange={(v) => {
            if (v === "graph" || v === "table") setViewMode(v as ViewMode)
          }}
          aria-label="View mode"
          className="self-start"
        >
          <ToggleGroupItem value="graph" className="gap-1.5 px-3">
            <Graph className="h-4 w-4" weight="duotone" aria-hidden />
            Graph
          </ToggleGroupItem>
          <ToggleGroupItem value="table" className="gap-1.5 px-3">
            <Table className="h-4 w-4" weight="duotone" aria-hidden />
            Table
          </ToggleGroupItem>
        </ToggleGroup>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] flex-1">
          <NucleoSearch
            size={NUCLEO_SIZE.row}
            aria-hidden
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[color:var(--g-text-muted)]"
          />
          <Input
            id="rel-search"
            aria-label="Search entities and links"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setPage(0)
            }}
            placeholder="Search names, types, or IDs…"
            className="pl-9"
          />
        </div>
        <Select
          value={perspective}
          onValueChange={(v) => {
            setPerspective(v)
            setPage(0)
          }}
        >
          <SelectTrigger className="min-w-[140px] flex-1 sm:w-[170px] sm:flex-none" aria-label="Perspective">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All relationships</SelectItem>
            <SelectItem value="organization">Organization</SelectItem>
            <SelectItem value="customers">Customers</SelectItem>
            <SelectItem value="agents">Agents</SelectItem>
            <SelectItem value="knowledge">Knowledge terms</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={typeFilter}
          onValueChange={(v) => {
            setTypeFilter(v)
            setPage(0)
          }}
        >
          <SelectTrigger className="min-w-[140px] flex-1 sm:w-[170px] sm:flex-none" aria-label="Relationship type">
            <SelectValue placeholder="All types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {relationshipTypes.map((t) => (
              <SelectItem key={t} value={t}>
                {relationshipTypeLabel(t)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
          <SelectTrigger className="min-w-[140px] flex-1 sm:w-[150px] sm:flex-none" aria-label="Sort">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="recent">Most recent</SelectItem>
            <SelectItem value="confidence">Confidence</SelectItem>
            <SelectItem value="evidence">Evidence count</SelectItem>
          </SelectContent>
        </Select>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button type="button" variant="outline" className="gap-1.5" aria-label="More filters">
              <SlidersHorizontal className="h-4 w-4" aria-hidden />
              {filterCount > 0 ? `Filters · ${filterCount}` : "Filters"}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuCheckboxItem
              checked={showArchived}
              onCheckedChange={(checked) => {
                setShowArchived(Boolean(checked))
                setPage(0)
              }}
            >
              Show archived
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={showTestData}
              onCheckedChange={(checked) => {
                setShowTestData(Boolean(checked))
                setPage(0)
              }}
            >
              Show test data
            </DropdownMenuCheckboxItem>
          </DropdownMenuContent>
        </DropdownMenu>
        {!hideAddEntity ? (
          <Button type="button" className="gap-1.5" onClick={() => openAddNode("entity")}>
            <Plus className="h-4 w-4" weight="bold" aria-hidden />
            Add entity
          </Button>
        ) : null}
      </div>
      {selection ? (
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Selected item">
          <span className="text-xs text-[color:var(--g-text-muted)]">Selected</span>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="gap-1.5"
            onClick={() => {
              setViewMode("graph")
              if (selection.kind === "node") {
                const seeded = nodes.find((n) => `seed::${n.id}` === selection.nodeId)
                const label = seeded
                  ? String(seeded.name ?? "")
                  : labelFor(selection.nodeId.split("::")[0], selection.nodeId.split("::").slice(1).join("::"))
                if (label) {
                  setQuery(label)
                  setPage(0)
                }
              }
            }}
          >
            <NucleoSearch size={NUCLEO_SIZE.row} aria-hidden />
            Focus
          </Button>
          {selection.kind === "node" ? (
            <>
              <Button
                type="button"
                size="sm"
                variant={neighborhoodOn ? "secondary" : "outline"}
                aria-pressed={neighborhoodOn}
                onClick={() => {
                  setViewMode("graph")
                  setNeighborhoodOn((on) => !on)
                }}
              >
                Neighborhood
              </Button>
              <Button
                type="button"
                size="sm"
                variant={pinnedIds.has(selection.nodeId) ? "secondary" : "outline"}
                aria-pressed={pinnedIds.has(selection.nodeId)}
                onClick={() => togglePin(selection.nodeId)}
              >
                Pin
              </Button>
            </>
          ) : null}
        </div>
      ) : null}
      {showTestData ? (
        <p
          className="rounded-md border border-amber-500/25 bg-amber-500/5 px-3 py-2 text-xs leading-relaxed text-[color:var(--g-text-secondary)]"
          data-testid="smoke-data-callout"
        >
          {RELATIONSHIPS_SMOKE_DATA.visibleCallout}
        </p>
      ) : null}
    </div>
  )
}
