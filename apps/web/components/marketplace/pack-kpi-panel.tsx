"use client"

import useSWR from "swr"
import { StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { intelligencePacksApi } from "@/lib/api"
import { cn } from "@/lib/utils"

export type PackKpiSummary = {
  packId: string
  installed: boolean
  installId?: string | null
  agentCount?: number
  workflowCount?: number
  signalsCount?: number
  entitiesCount?: number
  cacheTouches?: number
  assignmentsCount?: number
  vendors?: Record<string, { signals?: number; entities?: number }>
}

type PackKpiPanelProps = {
  packId: string
  packTitle?: string
  className?: string
  compact?: boolean
}

export function PackKpiPanel({
  packId,
  packTitle,
  className,
  compact = false,
}: PackKpiPanelProps) {
  const { data, error, isLoading } = useSWR(
    packId ? ["intelligence-pack-kpis", packId] : null,
    () => intelligencePacksApi.packKpis(packId),
    { revalidateOnFocus: false },
  )

  const title = packTitle || packId
  const kpis = data as PackKpiSummary | undefined

  return (
    <section
      data-testid="pack-kpi-panel"
      data-pack-id={packId}
      className={cn("rounded-lg border border-border/60 bg-card/40 p-4", className)}
      aria-label={`${title} pack KPIs`}
    >
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium tracking-tight">{title}</h3>
        <span className="text-xs text-muted-foreground">
          {isLoading
            ? "Loading…"
            : error
              ? "Unavailable"
              : kpis?.installed
                ? "Installed"
                : "Not installed"}
        </span>
      </div>
      <StatsGrid columns={compact ? 2 : 3}>
        <StatCard label="Signals" value={kpis?.signalsCount ?? "—"} />
        <StatCard label="Entities" value={kpis?.entitiesCount ?? "—"} />
        <StatCard label="Cache-linked" value={kpis?.cacheTouches ?? "—"} />
        {!compact ? (
          <>
            <StatCard label="Agents" value={kpis?.agentCount ?? "—"} />
            <StatCard label="Workflows" value={kpis?.workflowCount ?? "—"} />
            <StatCard label="Assignments" value={kpis?.assignmentsCount ?? "—"} />
          </>
        ) : null}
      </StatsGrid>
    </section>
  )
}
