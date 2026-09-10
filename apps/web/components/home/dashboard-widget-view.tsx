"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { GravitreMetric, GravitreSurface } from "@/components/gravitre/nodus-product/metric"
import {
  GravitreTable,
  GravitreTableShell,
  GravitreTd,
  GravitreTh,
} from "@/components/gravitre/nodus-product/table"
import { GravitreEmpty } from "@/components/gravitre/nodus-product/empty"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { KPI_BY_ID } from "@/lib/dashboard/kpi-registry"
import type { PlacedWidget } from "@/lib/dashboard/place-widgets"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import { formatModelLabel } from "@/hooks/use-home-dashboard-data"
import { relativeTime } from "@/lib/agent-job-result"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  NucleoAgent,
  NucleoArrowRight,
  NucleoHistory,
  NucleoIntelligence,
  NucleoSuccess,
} from "@/components/icons/nucleo/semantic"

const BRAND = "#16a374"
const BRAND_SOFT = "#5ec49a"
const MUTED = "#94a3b8"
const IDLE = "#cbd5e1"

function formatDuration(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "—"
  if (ms < 1000) return `${Math.round(ms)}ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${(seconds / 60).toFixed(1)}m`
}

function emptyLabel(kind: "runs" | "agents" | "generic"): string {
  if (kind === "runs") return "No runs yet"
  if (kind === "agents") return "No agents yet"
  return "No data yet"
}

const KPI_ICON_WRAPPER = "h-7 w-7"

const KPI_ICON_STYLES: Record<
  string,
  { icon: ReactNode; iconClassName: string; iconWrapperClassName: string }
> = {
  "agents.active": {
    icon: <NucleoAgent className="h-3.5 w-3.5 opacity-70" aria-hidden />,
    iconClassName: "bg-blue-500/8 text-blue-600/60",
    iconWrapperClassName: KPI_ICON_WRAPPER,
  },
  "runs.success_rate": {
    icon: <NucleoSuccess className="h-3.5 w-3.5 opacity-70" aria-hidden />,
    iconClassName: "bg-emerald-500/8 text-emerald-600/60",
    iconWrapperClassName: KPI_ICON_WRAPPER,
  },
  "runs.avg_duration": {
    icon: <NucleoHistory className="h-3.5 w-3.5 opacity-70" aria-hidden />,
    iconClassName: "bg-amber-500/8 text-amber-600/55",
    iconWrapperClassName: KPI_ICON_WRAPPER,
  },
  "models.most_used": {
    icon: <NucleoIntelligence className="h-3.5 w-3.5 opacity-70" aria-hidden />,
    iconClassName: "bg-[color:var(--g-brand)]/10 text-[color:var(--g-brand)]/60",
    iconWrapperClassName: KPI_ICON_WRAPPER,
  },
}

function MetricNumber({
  metricId,
  label,
  value,
  hint,
  href,
  warning,
}: {
  metricId?: string
  label: string
  value: string
  hint?: string
  href?: string
  warning?: boolean
}) {
  const iconStyle = metricId ? KPI_ICON_STYLES[metricId] : undefined
  return (
    <GravitreMetric
      label={label}
      value={value}
      hint={hint}
      href={href}
      warning={warning}
      icon={iconStyle?.icon}
      iconClassName={iconStyle?.iconClassName}
      iconWrapperClassName={iconStyle?.iconWrapperClassName}
      className="h-full"
    />
  )
}

function AgentsDonut({ data }: { data: HomeDashboardData }) {
  const counts = data.agentStatusCounts
  if (!counts) {
    return (
      <GravitreSurface className="h-full">
        <h2 className={TYPE.sectionTitle}>Agents by status</h2>
        <div className="mt-4">
          <GravitreEmpty title={emptyLabel("agents")} hint="Create an agent to populate this chart." />
        </div>
      </GravitreSurface>
    )
  }

  const slices = [
    { label: "Active", value: counts.active, color: BRAND },
    { label: "Executing", value: counts.processing, color: BRAND_SOFT },
    { label: "Idle", value: counts.idle, color: MUTED },
    { label: "Error", value: counts.error, color: "#f59e0b" },
  ].filter((s) => s.value > 0)
  const total = slices.reduce((sum, s) => sum + s.value, 0) || 1
  const circumference = 2 * Math.PI * 14
  let offset = 0

  return (
    <GravitreSurface className="h-full">
      <div className="flex items-start justify-between gap-3">
        <h2 className={TYPE.sectionTitle}>Agents by status</h2>
        <Link
          href={APP_ROUTES.agents}
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
        >
          View agents
          <NucleoArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="mt-4 flex flex-col gap-5 sm:flex-row sm:items-center">
        <div className="relative mx-auto flex h-32 w-32 shrink-0 items-center justify-center sm:mx-0">
          <svg viewBox="0 0 36 36" className="h-full w-full -rotate-90">
            <circle cx="18" cy="18" r="14" fill="none" className="stroke-muted" strokeWidth="3.5" />
            {slices.map((slice) => {
              const share = (slice.value / total) * circumference
              const node = (
                <circle
                  key={slice.label}
                  cx="18"
                  cy="18"
                  r="14"
                  fill="none"
                  stroke={slice.color}
                  strokeWidth="3.5"
                  strokeDasharray={`${share} ${circumference - share}`}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                />
              )
              offset += share
              return node
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="text-lg font-semibold tabular-nums text-foreground">{total}</span>
            <span className="text-[10px] text-muted-foreground">Agents</span>
          </div>
        </div>
        <ul className="flex-1 space-y-2.5">
          {[
            { label: "Active", value: counts.active, color: BRAND },
            { label: "Executing", value: counts.processing, color: BRAND_SOFT },
            { label: "Idle", value: counts.idle, color: MUTED },
            { label: "Error", value: counts.error, color: "#f59e0b" },
          ].map((row) => (
            <li key={row.label} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex items-center gap-2 text-muted-foreground">
                <span className="h-2 w-2 rounded-full" style={{ background: row.color }} />
                {row.label}
              </span>
              <span className="font-semibold tabular-nums text-foreground">{row.value}</span>
            </li>
          ))}
        </ul>
      </div>
    </GravitreSurface>
  )
}

function RunsBreakdown({ data }: { data: HomeDashboardData }) {
  const trend = data.metrics.trends.totalRuns
  const chartData =
    trend.length > 0
      ? trend.slice(-7).map((count, i) => ({
          name: `D${i + 1}`,
          completed: count,
          fill: i % 2 === 0 ? BRAND : BRAND_SOFT,
        }))
      : []

  return (
    <GravitreSurface className="h-full">
      <div className="flex items-start justify-between gap-3">
        <h2 className={TYPE.sectionTitle}>
          {chartData.length > 0 ? "Tasks breakdown" : "Tasks breakdown"}
        </h2>
        <Link
          href={APP_ROUTES.runs}
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
        >
          View runs
          <NucleoArrowRight className="h-3 w-3" />
        </Link>
      </div>
      {chartData.length === 0 ? (
        <div className="mt-4">
          <GravitreEmpty
            title={emptyLabel("runs")}
            hint="Waiting for first execution — run volume appears here."
          />
        </div>
      ) : (
        <div className="mt-3 h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" barSize={14} margin={{ left: 0, right: 8 }}>
              <XAxis type="number" hide domain={[0, "dataMax"]} />
              <YAxis
                type="category"
                dataKey="name"
                width={36}
                tick={{ fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip formatter={(value: number) => [`${value}`, "Runs"]} />
              <Bar dataKey="completed" radius={[0, 4, 4, 0]}>
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </GravitreSurface>
  )
}

function WorkflowMonitor({ data }: { data: HomeDashboardData }) {
  const rows = data.agents.slice(0, 8)
  return (
    <GravitreTableShell
      toolbar={
        <>
          <div>
            <h2 className={TYPE.sectionTitle}>Workflow monitor</h2>
            <p className={cn(TYPE.meta, "mt-0.5")}>Live agents — model, status, latency, last run</p>
          </div>
          <Link
            href={APP_ROUTES.agents}
            className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
          >
            View all
            <NucleoArrowRight className="h-3 w-3" />
          </Link>
        </>
      }
    >
      {rows.length === 0 ? (
        <div className="p-4">
          <GravitreEmpty title={emptyLabel("agents")} hint="Agents appear here once created." />
        </div>
      ) : (
        <GravitreTable>
          <thead>
            <tr>
              <GravitreTh>Agent</GravitreTh>
              <GravitreTh>Model</GravitreTh>
              <GravitreTh>Status</GravitreTh>
              <GravitreTh>Latency</GravitreTh>
              <GravitreTh>Last run</GravitreTh>
            </tr>
          </thead>
          <tbody>
            {rows.map((agent) => {
              const status = String(agent.status ?? "idle")
              const tone =
                status === "error"
                  ? "warning"
                  : status === "active" || status === "processing" || status === "running"
                    ? "success"
                    : "idle"
              return (
                <tr key={agent.id}>
                  <GravitreTd>
                    <Link href={`${APP_ROUTES.agents}/${agent.id}`} className="hover:underline">
                      {agent.name}
                    </Link>
                  </GravitreTd>
                  <GravitreTd>
                    <span className="text-muted-foreground">{agent.model?.trim() || "—"}</span>
                  </GravitreTd>
                  <GravitreTd>
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className={cn(
                          "h-1.5 w-1.5 rounded-full",
                          tone === "warning" && "bg-amber-500",
                          tone === "success" && "bg-[color:var(--brand)]",
                          tone === "idle" && "bg-muted-foreground/40",
                        )}
                        style={tone === "idle" ? { background: IDLE } : undefined}
                      />
                      <span className="text-xs font-medium capitalize">{status}</span>
                    </span>
                  </GravitreTd>
                  <GravitreTd>
                    <span className="text-muted-foreground">
                      {agent.stats?.avgResponseTime?.trim() || "—"}
                    </span>
                  </GravitreTd>
                  <GravitreTd>
                    <span className="text-muted-foreground">
                      {agent.lastActionTime ? relativeTime(agent.lastActionTime) : "—"}
                    </span>
                  </GravitreTd>
                </tr>
              )
            })}
          </tbody>
        </GravitreTable>
      )}
    </GravitreTableShell>
  )
}

function resolveKpiValue(
  metricId: string,
  data: HomeDashboardData,
): { value: string; hint?: string; href?: string; warning?: boolean; empty?: boolean } {
  const def = KPI_BY_ID[metricId]
  const href = def?.href
  switch (metricId) {
    case "agents.active":
      return {
        value: data.activeAgents != null ? String(data.activeAgents) : "—",
        hint:
          data.agentTotal != null
            ? `${data.activeAgents ?? 0} active · ${data.agentTotal} total →`
            : emptyLabel("agents"),
        href,
        empty: data.activeAgents == null,
      }
    case "agents.total":
      return {
        value: data.agentTotal != null ? String(data.agentTotal) : "—",
        hint: data.agentTotal != null ? "Workspace agents →" : emptyLabel("agents"),
        href,
        empty: data.agentTotal == null,
      }
    case "agents.idle":
      return {
        value: data.agentStatusCounts ? String(data.agentStatusCounts.idle) : "—",
        href,
        empty: !data.agentStatusCounts,
      }
    case "agents.executing":
      return {
        value: data.agentStatusCounts ? String(data.agentStatusCounts.processing) : "—",
        href,
        empty: !data.agentStatusCounts,
      }
    case "agents.error":
      return {
        value: data.agentStatusCounts ? String(data.agentStatusCounts.error) : "—",
        href,
        warning: (data.agentStatusCounts?.error ?? 0) > 0,
        empty: !data.agentStatusCounts,
      }
    case "workflows.active":
      return {
        value:
          data.metrics.activeWorkflows != null ? String(data.metrics.activeWorkflows) : "—",
        hint:
          data.metrics.activeWorkflows != null
            ? "Live workflow count →"
            : "No active workflows",
        href,
        empty: data.metrics.activeWorkflows == null,
      }
    case "workflows.total":
      return {
        value: data.metrics.totalWorkflows != null ? String(data.metrics.totalWorkflows) : "—",
        href,
        empty: data.metrics.totalWorkflows == null,
      }
    case "runs.success_rate":
      return {
        value: data.metrics.successRate != null ? `${data.metrics.successRate}%` : "—",
        hint:
          data.metrics.successRate != null
            ? data.metrics.changes.successRate != null
              ? `${data.metrics.changes.successRate >= 0 ? "+" : ""}${data.metrics.changes.successRate}% vs prior →`
              : "Verified runs →"
            : emptyLabel("runs"),
        href,
        empty: data.metrics.successRate == null,
      }
    case "runs.avg_duration":
      return {
        value: formatDuration(data.metrics.avgDuration),
        hint:
          data.metrics.avgDuration != null
            ? data.metrics.changes.avgLatency != null
              ? `${data.metrics.changes.avgLatency >= 0 ? "+" : ""}${Math.abs(data.metrics.changes.avgLatency)}% vs prior →`
              : "Mean run duration →"
            : "Waiting for runs",
        href,
        empty: data.metrics.avgDuration == null,
      }
    case "models.most_used":
      return {
        value: data.mostUsedModel ? formatModelLabel(data.mostUsedModel) : "—",
        hint: data.mostUsedModel ? "Across active agents →" : "Assign models to agents",
        href,
        empty: !data.mostUsedModel,
      }
    case "runs.total":
      return {
        value: data.metrics.totalRuns != null ? String(data.metrics.totalRuns) : "—",
        hint: data.metrics.totalRuns != null ? "Runs in range →" : emptyLabel("runs"),
        href,
        empty: data.metrics.totalRuns == null,
      }
    case "runs.avg_latency":
      return {
        value: formatDuration(data.metrics.avgLatency),
        href,
        empty: data.metrics.avgLatency == null,
      }
    case "approvals.pending":
      return {
        value: String(data.pendingApprovals),
        hint:
          data.pendingApprovals > 0
            ? `${data.pendingApprovals} awaiting decision →`
            : "Approvals clear →",
        href,
        warning: data.pendingApprovals > 0,
      }
    case "connectors.active":
      return {
        value:
          data.metrics.activeConnectors != null ? String(data.metrics.activeConnectors) : "—",
        href,
        empty: data.metrics.activeConnectors == null,
      }
    case "connectors.total":
      return {
        value: data.metrics.totalConnectors != null ? String(data.metrics.totalConnectors) : "—",
        href,
        empty: data.metrics.totalConnectors == null,
      }
    case "connectors.health_latency":
      return {
        value: formatDuration(data.metrics.connectorHealthLatencyMs),
        href,
        empty: data.metrics.connectorHealthLatencyMs == null,
      }
    case "gibe.avg_confidence":
      return {
        value: data.avgConfidence != null ? `${data.avgConfidence}%` : "—",
        hint: data.avgConfidence != null ? "Trust · 7d →" : "Confidence · not yet available",
        href,
        empty: data.avgConfidence == null,
      }
    case "system.ml_models_live":
      return {
        value: data.aiOs.mlModelsLive != null ? String(data.aiOs.mlModelsLive) : "—",
        href,
        empty: data.aiOs.mlModelsLive == null,
      }
    case "system.memory_promotions":
      return {
        value:
          data.aiOs.memoryPromotionsPending != null
            ? String(data.aiOs.memoryPromotionsPending)
            : "—",
        href,
        empty: data.aiOs.memoryPromotionsPending == null,
      }
    case "system.architecture_live":
      return {
        value:
          data.aiOs.architectureSystemsLive != null
            ? String(data.aiOs.architectureSystemsLive)
            : "—",
        href,
        empty: data.aiOs.architectureSystemsLive == null,
      }
    case "usage.records_processed":
      return {
        value:
          data.metrics.recordsProcessed != null
            ? data.metrics.recordsProcessed.toLocaleString()
            : "—",
        href,
        empty: data.metrics.recordsProcessed == null,
      }
    default:
      return { value: "—", href, empty: true }
  }
}

function ProgressWidget({
  title,
  percent,
  href,
}: {
  title: string
  percent: number
  href?: string
}) {
  return (
    <GravitreSurface className="h-full !p-3 sm:!p-3.5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-medium tracking-wide text-muted-foreground">{title}</p>
        {href ? (
          <Link href={href} className="text-[11px] text-[color:var(--brand)] hover:underline">
            Open
          </Link>
        ) : null}
      </div>
      <p className="mt-1 text-xl font-semibold tabular-nums">{percent}%</p>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-[color:var(--brand)]"
          style={{ width: `${Math.max(0, Math.min(100, percent))}%` }}
        />
      </div>
    </GravitreSurface>
  )
}

function ListWidget({
  title,
  items,
  href,
  emptyTitle,
}: {
  title: string
  items: Array<{ id: string; title: string; summary?: string }>
  href?: string
  emptyTitle: string
}) {
  return (
    <GravitreSurface className="h-full">
      <div className="flex items-start justify-between gap-2">
        <h2 className={TYPE.sectionTitle}>{title}</h2>
        {href ? (
          <Link
            href={href}
            className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--brand)] hover:underline"
          >
            View
            <NucleoArrowRight className="h-3 w-3" />
          </Link>
        ) : null}
      </div>
      {items.length === 0 ? (
        <div className="mt-3">
          <GravitreEmpty title={emptyTitle} hint="No items returned by the API." />
        </div>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.slice(0, 4).map((item) => (
            <li
              key={item.id}
              className="rounded-[var(--np-radius-md)] border border-divide px-3 py-2 text-sm"
            >
              <span className="font-medium text-foreground">{item.title}</span>
              {item.summary ? (
                <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{item.summary}</p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </GravitreSurface>
  )
}

export function DashboardWidgetView({
  widget,
  data,
}: {
  widget: PlacedWidget
  data: HomeDashboardData
}) {
  const def = KPI_BY_ID[widget.metricId]
  const title = widget.title ?? def?.name ?? widget.metricId

  if (widget.metricId === "agents.by_status") return <AgentsDonut data={data} />
  if (widget.metricId === "runs.breakdown") return <RunsBreakdown data={data} />
  if (widget.metricId === "agents.monitor") return <WorkflowMonitor data={data} />
  if (widget.metricId === "gibe.learning_query") {
    const needed = data.queryRowsNeeded || 50
    const percent = Math.round(Math.max(0, Math.min(100, (data.queryRows / needed) * 100)))
    return <ProgressWidget title={title} percent={percent} href={def?.href} />
  }
  if (widget.metricId === "gibe.learning_workflow") {
    const needed = data.workflowRowsNeeded || 30
    const percent = Math.round(Math.max(0, Math.min(100, (data.workflowRows / needed) * 100)))
    return <ProgressWidget title={title} percent={percent} href={def?.href} />
  }
  if (widget.metricId === "gibe.revenue_risks") {
    return (
      <ListWidget
        title={title}
        items={data.revenueRisks}
        href={def?.href}
        emptyTitle="No signals this period"
      />
    )
  }
  if (widget.metricId === "gibe.predictive") {
    return (
      <GravitreSurface className="h-full">
        <h2 className={TYPE.sectionTitle}>{title}</h2>
        {data.predictiveSummary ? (
          <p className={cn(TYPE.bodyMuted, "mt-3")}>{data.predictiveSummary}</p>
        ) : (
          <div className="mt-3">
            <GravitreEmpty
              title="No forecast summary yet"
              hint="Appears once enough run history exists."
            />
          </div>
        )}
      </GravitreSurface>
    )
  }
  if (widget.metricId === "approvals.pending" && widget.size !== "1x1" && data.pendingApprovals > 0) {
    return (
      <ListWidget
        title={title}
        items={data.pendingApprovalItems.map((i) => ({
          id: i.id,
          title: i.title ?? i.id,
        }))}
        href={APP_ROUTES.approvals}
        emptyTitle="Approvals clear"
      />
    )
  }

  const resolved = resolveKpiValue(widget.metricId, data)
  const showTrend =
    widget.visualization === "number_trend" ||
    widget.visualization === "sparkline" ||
    widget.size === "2x1" ||
    widget.size === "2x2"

  let trendHint = resolved.hint
  if (showTrend && widget.metricId === "runs.success_rate" && data.metrics.changes.successRate != null) {
    const d = data.metrics.changes.successRate
    trendHint = `${d >= 0 ? "+" : ""}${d}% vs prior period`
  }

  return (
    <MetricNumber
      metricId={widget.metricId}
      label={title}
      value={resolved.empty && resolved.value === "—" ? "—" : resolved.value}
      hint={
        resolved.empty && resolved.value === "—"
          ? trendHint ?? "Waiting for first execution"
          : trendHint
      }
      href={resolved.href}
      warning={resolved.warning}
    />
  )
}
