"use client"

import type { ReactNode } from "react"
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
  toolbarEnd,
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
  /** Right-side actions on the view/sort row (e.g. Minimize). */
  toolbarEnd?: ReactNode
  className?: string
}) {
  const hasFilters = Boolean(
    filters.department || filters.status || filters.role || filters.model,
  )

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <SegmentedControl
          ariaLabel="Fleet view"
          options={VIEW_OPTIONS}
          value={view}
          onChange={onViewChange}
        />
        <label className="flex items-center gap-1.5 text-xs text-[color:var(--g-text-muted)]">
          <span className="sr-only sm:not-sr-only">Sort</span>
          <select
            value={sort}
            onChange={(e) => onSortChange(e.target.value as AgentsFleetSortId)}
            className="h-8 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-xs text-[color:var(--g-text-primary)]"
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
          className="h-8 rounded-md border border-divide px-2 text-xs text-[color:var(--g-text-muted)] hover:text-[color:var(--g-text-primary)]"
          aria-label={`Sort direction ${sortDir}`}
          title={sortDir === "asc" ? "Ascending" : "Descending"}
        >
          {sortDir === "asc" ? "↑" : "↓"}
        </button>
        {hasFilters ? (
          <button
            type="button"
            onClick={onClearFilters}
            className="h-8 rounded-md px-2 text-xs font-medium text-[color:var(--g-brand)]"
          >
            Clear filters
          </button>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden text-[11px] text-[color:var(--g-text-muted)] lg:inline">
            Edges: parent · swarm · connectors
          </span>
          {toolbarEnd}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        {searchSlot ? <div className="min-w-[12rem] flex-[2_1_14rem]">{searchSlot}</div> : null}
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
  )
}

/** Slim strip when filters chrome is minimized — view switch only. */
export function FleetControlsCollapsed({
  view,
  onViewChange,
  onShowFilters,
  className,
}: {
  view: AgentsFleetViewPref
  onViewChange: (view: AgentsFleetViewPref) => void
  onShowFilters: () => void
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      <SegmentedControl
        ariaLabel="Fleet view"
        options={VIEW_OPTIONS}
        value={view}
        onChange={onViewChange}
      />
      <button
        type="button"
        onClick={onShowFilters}
        className="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md px-2 text-xs text-[color:var(--g-text-muted)] transition-colors hover:bg-[color:var(--g-surface-active)] hover:text-[color:var(--g-text-primary)]"
        aria-label="Show filters"
      >
        <span className="text-[11px]">Show filters</span>
      </button>
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
      <span className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
        {label}
      </span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? e.target.value : null)}
        className="h-8 rounded-md border border-divide bg-[color:var(--g-surface-1)] px-2 text-xs text-[color:var(--g-text-primary)]"
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
