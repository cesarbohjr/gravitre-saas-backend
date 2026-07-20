"use client"

import useSWR from "swr"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { workflowsApi } from "@/lib/api"
import { cn } from "@/lib/utils"

type OutcomeBucket = {
  pass: number
  fail: number
  cancel: number
  pass_rate: number | null
}

type SourceRow = OutcomeBucket & { source: string }
type ConnectorRow = OutcomeBucket & { connector: string }

type OpsSummary = {
  window_hours: number
  totals: OutcomeBucket & { other?: number }
  pass_rate: number | null
  by_source: SourceRow[]
  by_connector: ConnectorRow[]
  event_count: number
}

function pct(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return "—"
  return `${Math.round(rate * 100)}%`
}

export function OutcomeOpsPanel({ className }: { className?: string }) {
  const { data, error, isLoading } = useSWR(
    ["execution-outcomes-ops-summary"],
    () => workflowsApi.executionOutcomesOpsSummary(),
    { revalidateOnFocus: true, refreshInterval: 60_000 },
  )

  const summary = data as OpsSummary | undefined
  const topSources = (summary?.by_source ?? []).slice(0, 4)
  const topConnectors = (summary?.by_connector ?? []).slice(0, 4)

  return (
    <section
      data-testid="outcome-ops-panel"
      className={cn("rounded-lg border border-border/60 bg-card/40 p-4", className)}
      aria-label="Execution outcomes last 24 hours"
    >
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium tracking-tight">Execution outcomes (24h)</h3>
        <span className="text-xs text-muted-foreground">
          {isLoading ? "Loading…" : error ? "Unavailable" : `${summary?.event_count ?? 0} events`}
        </span>
      </div>
      <StatsGrid columns={3}>
        <StatCard label="Pass rate" value={pct(summary?.pass_rate)} variant="info" />
        <StatCard label="Passed" value={summary?.totals?.pass ?? "—"} variant="success" />
        <StatCard label="Failed" value={summary?.totals?.fail ?? "—"} variant="danger" />
      </StatsGrid>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">By trigger source</p>
          <ul className="space-y-1.5 text-sm">
            {topSources.length === 0 ? (
              <li className="text-muted-foreground">No outcomes in window</li>
            ) : (
              topSources.map((row) => (
                <li key={row.source} className="flex items-center justify-between gap-2">
                  <span className="truncate">{row.source}</span>
                  <span className="shrink-0 text-muted-foreground">
                    {row.pass}/{row.fail} · {pct(row.pass_rate)}
                  </span>
                </li>
              ))
            )}
          </ul>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">By connector</p>
          <ul className="space-y-1.5 text-sm">
            {topConnectors.length === 0 ? (
              <li className="text-muted-foreground">No connector-tagged outcomes</li>
            ) : (
              topConnectors.map((row) => (
                <li key={row.connector} className="flex items-center justify-between gap-2">
                  <span className="truncate">{row.connector}</span>
                  <span className="shrink-0 text-muted-foreground">
                    {row.pass}/{row.fail} · {pct(row.pass_rate)}
                  </span>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>
    </section>
  )
}
