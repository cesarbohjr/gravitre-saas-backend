"use client"

import useSWR from "swr"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
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
      <section
        className={cn(
          "grid gap-[var(--np-kpi-gap)]",
          compact ? "grid-cols-2" : "grid-cols-2 lg:grid-cols-3",
        )}
      >
        <GravitreMetric label="Signals" value={kpis?.signalsCount ?? "—"} />
        <GravitreMetric label="Entities" value={kpis?.entitiesCount ?? "—"} />
        <GravitreMetric label="Cache-linked" value={kpis?.cacheTouches ?? "—"} />
        {!compact ? (
          <>
            <GravitreMetric label="Agents" value={kpis?.agentCount ?? "—"} />
            <GravitreMetric label="Workflows" value={kpis?.workflowCount ?? "—"} />
            <GravitreMetric label="Assignments" value={kpis?.assignmentsCount ?? "—"} />
          </>
        ) : null}
      </section>
    </section>
  )
}
