"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { relationshipTypeLabel } from "@/lib/learning-ui-copy"
import type { SortKey, ViewMode } from "@/lib/relationships-graph/types"
import { Graph, Plus, Table } from "@phosphor-icons/react"
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
    relationshipTypes,
    filtered,
    relationships,
    openAddNode,
    showTestData,
    setShowTestData,
    perspective,
    setPerspective,
  } = workspace

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={viewMode}
          onValueChange={(v) => {
            if (v === "graph" || v === "table") setViewMode(v as ViewMode)
          }}
          aria-label="View mode"
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
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="font-normal tabular-nums">
            {filtered.length} shown
            {relationships.length !== filtered.length ? ` of ${relationships.length}` : ""}
          </Badge>
          {!hideAddEntity ? (
            <Button type="button" size="sm" className="gap-1.5" onClick={() => openAddNode("entity")}>
              <Plus className="h-4 w-4" weight="bold" aria-hidden />
              Add entity
            </Button>
          ) : null}
        </div>
      </div>
      <div className="flex flex-col gap-3 lg:flex-row lg:flex-wrap lg:items-end">
        <div className="min-w-0 flex-1 space-y-1.5">
          <label htmlFor="rel-search" className="text-xs font-medium text-[color:var(--g-text-muted)]">
            Search
          </label>
          <Input
            id="rel-search"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setPage(0)
            }}
            placeholder="Search names, types, or IDs…"
            className="max-w-md"
          />
        </div>
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Perspective</span>
          <Select
            value={perspective}
            onValueChange={(v) => {
              setPerspective(v)
              setPage(0)
            }}
          >
            <SelectTrigger className="w-[180px]">
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
        </div>
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Relationship type</span>
          <Select
            value={typeFilter}
            onValueChange={(v) => {
              setTypeFilter(v)
              setPage(0)
            }}
          >
            <SelectTrigger className="w-[200px]">
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
        </div>
        <div className="space-y-1.5">
          <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Sort</span>
          <Select value={sortKey} onValueChange={(v) => setSortKey(v as SortKey)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="recent">Most recent</SelectItem>
              <SelectItem value="confidence">Confidence</SelectItem>
              <SelectItem value="evidence">Evidence count</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          variant={showArchived ? "secondary" : "outline"}
          size="sm"
          onClick={() => {
            setShowArchived((v) => !v)
            setPage(0)
          }}
        >
          {showArchived ? "Showing archived" : "Show archived"}
        </Button>
        <Button
          type="button"
          variant={showTestData ? "secondary" : "outline"}
          size="sm"
          onClick={() => {
            setShowTestData((v) => !v)
            setPage(0)
          }}
        >
          {showTestData ? "Including test data" : "Show test data"}
        </Button>
      </div>
    </div>
  )
}
