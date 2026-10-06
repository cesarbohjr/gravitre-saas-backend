"use client"

import { useState, type ReactNode } from "react"
import { SlidersHorizontal } from "lucide-react"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { cn } from "@/lib/utils"
import type {
  AgentsFleetFilters,
  AgentsFleetSortId,
  AgentsFleetViewPref,
} from "@/lib/agents-fleet-prefs"

const VIEW_OPTIONS = [
  { id: "team" as const, label: "Team" },
  { id: "list" as const, label: "List" },
  { id: "graph" as const, label: "Graph" },
]

const SORT_OPTIONS: { id: AgentsFleetSortId; label: string }[] = [
  { id: "name", label: "Name" },
  { id: "department", label: "Department" },
  { id: "status", label: "Status" },
  { id: "tasks_today", label: "Tasks today" },
  { id: "success_rate", label: "Success rate" },
  { id: "last_active", label: "Last active" },
]

const STATUS_OPTIONS = [
  { id: "available", label: "Available" },
  { id: "executing", label: "Executing" },
  { id: "idle", label: "Idle" },
  { id: "failed", label: "Failed" },
  { id: "offline", label: "Offline" },
  { id: "waiting_approval", label: "Waiting approval" },
]

export function FleetControls({
  view,
  onViewChange,
  sort,
  sortDir,
  onSortChange,
  onToggleSortDir,
  filters,
  onFiltersChange,
  onClearFilters,
  departments,
  roles,
  models,
  searchSlot,
  className,
}: {
  view: AgentsFleetViewPref
  onViewChange: (view: AgentsFleetViewPref) => void
  sort: AgentsFleetSortId
  sortDir: "asc" | "desc"
  onSortChange: (sort: AgentsFleetSortId) => void
  onToggleSortDir: () => void
  filters: AgentsFleetFilters
  onFiltersChange: (patch: Partial<AgentsFleetFilters>) => void
  onClearFilters: () => void
  departments: string[]
  roles: string[]
  models: string[]
  /** Search field — rendered on the same row as department/status/role/model. */
  searchSlot?: ReactNode
  className?: string
}) {
  const [filtersOpen, setFiltersOpen] = useState(false)
  const activeFilterCount = [filters.department, filters.status, filters.role, filters.model].filter(Boolean).length
  const hasFilters = activeFilterCount > 0

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        {searchSlot ? <div className="min-w-0 flex-1 lg:max-w-md">{searchSlot}</div> : null}
        <button
          type="button"
          onClick={() => setFiltersOpen((open) => !open)}
          aria-expanded={filtersOpen}
          aria-controls="fleet-filters"
          className={cn(
            "inline-flex min-h-11 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-medium lg:hidden",
            hasFilters
              ? "border-[color:var(--g-emerald)] text-[color:var(--g-text-primary)]"
              : "border-divide text-[color:var(--g-text-secondary)]",
          )}
        >
          <SlidersHorizontal className="size-4" aria-hidden />
          Filters
          {hasFilters ? (
            <span className="rounded-full bg-[color:var(--g-emerald)] px-1.5 text-xs tabular-nums text-[color:var(--g-canvas)]">
              {activeFilterCount}
            </span>
          ) : null}
        </button>
      </div>

      <div
        id="fleet-filters"
        className={cn("flex-col gap-2 lg:flex", filtersOpen ? "flex" : "hidden")}
      >
      <div className="flex flex-wrap items-center gap-2">
        <SegmentedControl
          ariaLabel="Fleet view"
          options={VIEW_OPTIONS}
          value={view}
          onChange={onViewChange}
          className="[&>button]:min-h-10 lg:[&>button]:min-h-0"
        />
        <label className="flex items-center gap-1.5 text-xs text-[color:var(--g-text-muted)]">
          <span className="sr-only sm:not-sr-only">Sort</span>
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as AgentsFleetSortId)}
            className="h-11 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-sm text-[color:var(--g-text-primary)] lg:h-8 lg:text-xs"
            aria-label="Sort agents"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onToggleSortDir}
          className="h-11 min-w-11 rounded-md border border-divide px-2 text-sm text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)] lg:h-8 lg:min-w-0 lg:text-xs"
          aria-label={`Sort direction ${sortDir}`}
          title={sortDir === "asc" ? "Ascending" : "Descending"}
        >
          {sortDir === "asc" ? "↑" : "↓"}
        </button>
        {hasFilters ? (
          <button
            type="button"
            onClick={onClearFilters}
            className="h-11 rounded-md px-2 text-sm font-medium text-[color:var(--g-brand)] lg:h-8 lg:text-xs"
          >
            Clear filters
          </button>
        ) : null}
        {view === "graph" ? (
          <span className="ml-auto hidden text-[11px] text-[color:var(--g-text-muted)] xl:inline">
            Edges: parent · swarm · connectors
          </span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <FilterSelect
          label="Department"
          value={filters.department}
          options={departments}
          onChange={(department) => onFiltersChange({ department })}
        />
        <FilterSelect
          label="Status"
          value={filters.status}
          options={STATUS_OPTIONS.map((s) => s.id)}
          optionLabels={Object.fromEntries(STATUS_OPTIONS.map((s) => [s.id, s.label]))}
          onChange={(status) => onFiltersChange({ status })}
        />
        <FilterSelect
          label="Role"
          value={filters.role}
          options={roles}
          onChange={(role) => onFiltersChange({ role })}
        />
        <FilterSelect
          label="Model"
          value={filters.model}
          options={models.filter((m) => m && m !== "—")}
          onChange={(model) => onFiltersChange({ model })}
        />
      </div>
      </div>
    </div>
  )
}

/** Slim strip when roster chrome is minimized — view switch only. */
export function FleetControlsCollapsed({
  view,
  onViewChange,
  className,
}: {
  view: AgentsFleetViewPref
  onViewChange: (view: AgentsFleetViewPref) => void
  className?: string
}) {
  return (
    <div className={cn("flex min-w-0 flex-1 flex-wrap items-center gap-2", className)}>
      <SegmentedControl
        ariaLabel="Fleet view"
        options={VIEW_OPTIONS}
        value={view}
        onChange={onViewChange}
      />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  options,
  optionLabels,
  onChange,
}: {
  label: string
  value: string | null
  options: string[]
  optionLabels?: Record<string, string>
  onChange: (value: string | null) => void
}) {
  return (
    <label className="flex min-w-[7.5rem] flex-1 flex-col gap-0.5 sm:max-w-[9.5rem]">
      <span className="text-xs font-medium text-[color:var(--g-text-muted)]">
        {label}
      </span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? e.target.value : null)}
        className="h-11 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-sm text-[color:var(--g-text-primary)] lg:h-8 lg:text-xs"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {optionLabels?.[opt] ?? opt}
          </option>
        ))}
      </select>
    </label>
  )
}
