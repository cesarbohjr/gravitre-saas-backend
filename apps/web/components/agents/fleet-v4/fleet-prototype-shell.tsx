"use client"

import { useMemo, useState } from "react"
import { SegmentedControl } from "@/components/gravitre/filter-chip"
import { NucleoSearch } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { AgentAppearancePicker } from "./appearance-picker"
import { AgentInspector } from "./agent-inspector"
import { CurrentVsProposed } from "./current-vs-proposed"
import { FleetSummaryBar } from "./fleet-summary"
import { FLEET_FIXTURE_AGENTS, FLEET_FIXTURE_EDGES, FLEET_FIXTURE_EXTRA_NODES, FLEET_SUMMARY } from "./fixtures"
import { GraphView } from "./graph-view"
import { GravitreAgentIdentity } from "./gravitre-agent-identity"
import { ListView } from "./list-view"
import { TeamView } from "./team-view"
import type { AgentFleetView } from "./types"

const VIEW_OPTIONS = [
  { id: "team" as const, label: "Team" },
  { id: "list" as const, label: "List" },
  { id: "graph" as const, label: "Graph" },
]

export type PrototypeScreen =
  | "identity"
  | "team"
  | "team-grouped"
  | "list"
  | "graph"
  | "graph-run"
  | "inspector"
  | "picker"
  | "narrow"
  | "mobile"
  | "compare"
  | "shell"

export function FleetPrototypeShell({
  screen = "shell",
  forceView,
  forceNarrow,
  forceMobile,
  openInspectorOnMount,
  showExecution,
}: {
  screen?: PrototypeScreen
  forceView?: AgentFleetView
  forceNarrow?: boolean
  forceMobile?: boolean
  openInspectorOnMount?: boolean
  showExecution?: boolean
}) {
  const [view, setView] = useState<AgentFleetView>(forceView ?? "team")
  const [selectedId, setSelectedId] = useState<string | null>(
    openInspectorOnMount || screen === "inspector" ? (FLEET_FIXTURE_AGENTS[0]?.id ?? null) : null,
  )
  const [query, setQuery] = useState("")

  const agents = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return FLEET_FIXTURE_AGENTS
    return FLEET_FIXTURE_AGENTS.filter((a) =>
      [a.name, a.role, a.departmentLabel, a.model, a.runtimeState, ...a.tools, ...a.workflows]
        .join(" ")
        .toLowerCase()
        .includes(q),
    )
  }, [query])

  const selected = FLEET_FIXTURE_AGENTS.find((a) => a.id === selectedId) ?? null
  const activeView: AgentFleetView =
    forceView ??
    (screen === "list" || screen === "mobile"
      ? "list"
      : screen === "graph" || screen === "graph-run"
        ? "graph"
        : screen === "team" || screen === "team-grouped" || screen === "inspector" || screen === "narrow"
          ? "team"
          : view)

  const execution = showExecution || screen === "graph-run"
  const grouped = screen !== "team"
  const inspectorOpen =
    Boolean(selected) &&
    (screen === "inspector" ||
      screen === "shell" ||
      screen === "team" ||
      screen === "team-grouped" ||
      screen === "list" ||
      screen === "graph" ||
      screen === "graph-run" ||
      screen === "narrow" ||
      screen === "mobile")

  if (screen === "identity") {
    return (
      <div className="space-y-4 p-4 sm:p-6">
        <p className="text-xs text-[color:var(--g-text-muted)]">
          Identity sizes sm / md / lg — status as overlay dot only.
        </p>
        <div className="flex flex-wrap items-end gap-6">
          {(["sm", "md", "lg"] as const).map((size) => (
            <div key={size} className="flex flex-col items-center gap-2">
              <GravitreAgentIdentity
                icon="sales"
                identityColor="violet"
                status="executing"
                size={size}
                variant="card"
              />
              <span className="text-[10px] uppercase text-[color:var(--g-text-muted)]">{size}</span>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-3">
          {FLEET_FIXTURE_AGENTS.map((a) => (
            <GravitreAgentIdentity
              key={a.id}
              icon={a.icon}
              identityColor={a.identityColor}
              status={a.runtimeState}
              variant="card"
            />
          ))}
        </div>
      </div>
    )
  }

  if (screen === "picker") {
    return (
      <div className="p-4 sm:p-6">
        <AgentAppearancePicker />
      </div>
    )
  }

  if (screen === "compare") {
    return (
      <div className="p-4 sm:p-6">
        <CurrentVsProposed />
      </div>
    )
  }

  return (
    <div
      className={cn(
        "space-y-4 p-4 sm:p-6",
        forceMobile && "mx-auto max-w-[390px] px-3",
        forceNarrow && !forceMobile && "mx-auto max-w-[1024px]",
      )}
    >
      <FleetSummaryBar counts={FLEET_SUMMARY} />

      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          ariaLabel="Fleet view"
          options={VIEW_OPTIONS}
          value={activeView}
          onChange={setView}
        />
        <div className="relative min-w-[160px] flex-1">
          <NucleoSearch className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[color:var(--g-text-muted)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search name, role, dept, tool…"
            className="h-9 w-full rounded-md border border-divide bg-[color:var(--g-surface-1)] pl-8 pr-3 text-sm outline-none focus:border-[color:var(--g-brand-border)]"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="h-9 rounded-md bg-foreground px-3 text-xs font-medium text-background"
          >
            New Agent
          </button>
          <button
            type="button"
            className="h-9 rounded-md border border-divide px-3 text-xs font-medium text-[color:var(--g-text-muted)]"
          >
            Multi-Agent Run
          </button>
          {!forceMobile ? (
            <button
              type="button"
              className="h-9 rounded-md border border-divide px-3 text-xs font-medium text-[color:var(--g-text-muted)]"
            >
              Build with Meson
            </button>
          ) : null}
        </div>
      </div>

      {activeView === "team" ? (
        <TeamView
          agents={agents}
          selectedId={selectedId}
          onSelect={setSelectedId}
          grouped={grouped}
        />
      ) : null}
      {activeView === "list" ? (
        <ListView agents={agents} selectedId={selectedId} onSelect={setSelectedId} />
      ) : null}
      {activeView === "graph" ? (
        <GraphView
          agents={agents}
          edges={
            execution
              ? FLEET_FIXTURE_EDGES
              : FLEET_FIXTURE_EDGES.map((e) => ({ ...e, active: false }))
          }
          extraNodes={FLEET_FIXTURE_EXTRA_NODES}
          selectedId={selectedId}
          onSelect={setSelectedId}
          activeAgentIds={
            execution
              ? new Set(
                  FLEET_FIXTURE_EDGES.filter((e) => e.active).flatMap((e) => [
                    e.source,
                    e.target,
                  ]),
                )
              : undefined
          }
        />
      ) : null}

      <AgentInspector
        agent={selected}
        open={inspectorOpen && Boolean(selected)}
        onOpenChange={(open) => {
          if (!open) setSelectedId(null)
        }}
      />
    </div>
  )
}
