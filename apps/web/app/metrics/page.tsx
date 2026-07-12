"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { apiFetch } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { metricsApi } from "@/lib/api"
import type { MetricInsight } from "@/types/api"
import { 
  Calendar, 
  Download, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown, 
  AlertCircle,
  Sparkles,
  Activity,
  Zap,
  Clock,
  CheckCircle2,
  XCircle,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  Eye,
  Check
} from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { toast } from "sonner"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ReferenceLine,
} from "recharts"

type ThroughputDay = {
  day: string
  records: number
  target: number
}

const WEEKDAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

function normalizeWeeklyThroughput(payload: unknown): { days: ThroughputDay[]; target: number } {
  const emptyDays = WEEKDAY_ORDER.map((day) => ({ day, records: 0, target: 0 }))
  if (!payload || typeof payload !== "object") {
    return { days: emptyDays, target: 0 }
  }
  const model = payload as Record<string, unknown>
  const target = parseNumber(model.target, 0)
  const raw = Array.isArray(model.days) ? model.days : null
  if (!raw) {
    return { days: emptyDays.map((entry) => ({ ...entry, target })), target }
  }
  const byDay = new Map<string, ThroughputDay>()
  for (const item of raw) {
    if (!item || typeof item !== "object") continue
    const row = item as Record<string, unknown>
    const day = String(row.day ?? "")
    if (!day) continue
    byDay.set(day, {
      day,
      records: parseNumber(row.records, 0),
      target: parseNumber(row.target, target),
    })
  }
  return {
    days: WEEKDAY_ORDER.map(
      (day) => byDay.get(day) ?? { day, records: 0, target }
    ),
    target,
  }
}

type MetricsOverview = {
  totalRuns: number
  successRate: number
  recordsProcessed: number
  avgLatency: number
  activeConnectors: number
  totalConnectors: number
  changes: {
    totalRuns: number
    successRate: number
    recordsProcessed: number
    avgLatency: number
  }
  trends: {
    totalRuns: number[]
    successRate: number[]
    recordsProcessed: number[]
    avgLatency: number[]
  }
}

function parseNumber(value: unknown, defaultValue = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (trimmed.endsWith("M")) {
      const scaled = Number.parseFloat(trimmed.slice(0, -1))
      return Number.isFinite(scaled) ? scaled * 1_000_000 : defaultValue
    }
    const parsed = Number.parseFloat(trimmed.replace(/,/g, ""))
    return Number.isFinite(parsed) ? parsed : defaultValue
  }
  return defaultValue
}

function formatRecordsCount(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`
  return count.toLocaleString()
}

function normalizeOverview(payload: unknown): MetricsOverview {
  const empty: MetricsOverview = {
    totalRuns: 0,
    successRate: 0,
    recordsProcessed: 0,
    avgLatency: 0,
    activeConnectors: 0,
    totalConnectors: 0,
    changes: {
      totalRuns: 0,
      successRate: 0,
      recordsProcessed: 0,
      avgLatency: 0,
    },
    trends: {
      totalRuns: [],
      successRate: [],
      recordsProcessed: [],
      avgLatency: [],
    },
  }
  if (!payload || typeof payload !== "object") return empty
  const model = payload as Record<string, unknown>
  return {
    totalRuns: parseNumber(model.totalRuns, 0),
    successRate: parseNumber(model.successRate, 0),
    recordsProcessed: parseNumber(model.recordsProcessed, 0),
    avgLatency: parseNumber(model.avgLatency, 0),
    activeConnectors: parseNumber(model.activeConnectors, 0),
    totalConnectors: parseNumber(model.totalConnectors, 0),
    changes: {
      totalRuns: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.totalRuns ?? model.totalRunsChange,
        0
      ),
      successRate: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.successRate ?? model.successRateChange,
        0
      ),
      recordsProcessed: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.recordsProcessed ??
          model.recordsProcessedChange,
        0
      ),
      avgLatency: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.avgLatency ?? model.avgLatencyChange,
        0
      ),
    },
    trends: {
      totalRuns: Array.isArray((model.trends as Record<string, unknown> | undefined)?.totalRuns)
        ? ((model.trends as Record<string, unknown>).totalRuns as unknown[]).map((v) => parseNumber(v, 0))
        : [],
      successRate: Array.isArray((model.trends as Record<string, unknown> | undefined)?.successRate)
        ? ((model.trends as Record<string, unknown>).successRate as unknown[]).map((v) => parseNumber(v, 0))
        : [],
      recordsProcessed: Array.isArray((model.trends as Record<string, unknown> | undefined)?.recordsProcessed)
        ? ((model.trends as Record<string, unknown>).recordsProcessed as unknown[]).map((v) => parseNumber(v, 0))
        : [],
      avgLatency: Array.isArray((model.trends as Record<string, unknown> | undefined)?.avgLatency)
        ? ((model.trends as Record<string, unknown>).avgLatency as unknown[]).map((v) => parseNumber(v, 0))
        : [],
    },
  }
}

function normalizeSeries(payload: unknown) {
  const empty = {
    runVolume: [] as Record<string, unknown>[],
    latencyDistribution: [] as Record<string, unknown>[],
    latencySpikeTime: null as string | null,
  }
  if (!payload || typeof payload !== "object") return empty
  const model = payload as Record<string, unknown>
  const rawRunVolume = Array.isArray(model.runVolume)
    ? model.runVolume
    : Array.isArray(model.series)
      ? model.series
      : null
  return {
    runVolume: rawRunVolume
      ? (rawRunVolume as Record<string, unknown>[]).map((entry) => ({
          ...entry,
          time: String(entry.time ?? entry.timestamp ?? entry.hour ?? "Now"),
          completed: Number(entry.completed ?? 0),
          failed: Number(entry.failed ?? 0),
        }))
      : empty.runVolume,
    latencyDistribution: Array.isArray(model.latencyDistribution)
      ? (model.latencyDistribution as Record<string, unknown>[]).map((entry) => ({
          ...entry,
          time: String(entry.time ?? entry.hour ?? "Now"),
        }))
      : empty.latencyDistribution,
    latencySpikeTime:
      typeof model.latencySpikeTime === "string" && model.latencySpikeTime.trim()
        ? model.latencySpikeTime
        : null,
  }
}

function normalizeInsights(payload: unknown): MetricInsight[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.insights) ? model.insights : null
  if (!raw) return []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item, index): MetricInsight => {
      const type: MetricInsight["type"] =
        item.type === "anomaly" || item.type === "trend" || item.type === "optimization"
          ? item.type
          : "trend"
      const severity: MetricInsight["severity"] =
        item.severity === "info" ||
        item.severity === "warning" ||
        item.severity === "critical" ||
        item.severity === "success"
          ? item.severity
          : "info"
      return {
        id: String(item.id ?? `insight-${index + 1}`),
        type,
        severity,
        title: String(item.title ?? "Insight"),
        description: String(item.description ?? ""),
        timestamp: String(item.timestamp ?? "recently"),
        relatedWorkflowId: item.relatedWorkflowId ? String(item.relatedWorkflowId) : undefined,
        relatedRunId: item.relatedRunId ? String(item.relatedRunId) : undefined,
        relatedConnectorId: item.relatedConnectorId ? String(item.relatedConnectorId) : undefined,
        suggestedAction: item.suggestedAction ? String(item.suggestedAction) : undefined,
      }
    })
}

// Metric card with trend visualization
function MetricCard({ 
  title, 
  value, 
  change, 
  changeLabel,
  icon: Icon,
  trend,
  accentColor = "blue"
}: { 
  title: string
  value: string
  change?: number
  changeLabel?: string
  icon: typeof Activity
  trend?: number[]
  accentColor?: "blue" | "emerald" | "amber" | "red"
}) {
  const isPositive = change === undefined ? null : change >= 0
  const colorClasses = {
    blue: "from-blue-500/20 to-blue-500/5 text-blue-400",
    emerald: "from-emerald-500/20 to-emerald-500/5 text-emerald-400",
    amber: "from-amber-500/20 to-amber-500/5 text-amber-400",
    red: "from-red-500/20 to-red-500/5 text-red-400",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="relative overflow-hidden rounded-xl border border-border bg-card"
    >
      {/* Background gradient */}
      <div className={cn(
        "absolute inset-0 bg-gradient-to-br opacity-30",
        colorClasses[accentColor]
      )} />
      
      <div className="relative p-4">
        <div className="flex items-start justify-between mb-3">
          <div className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg",
            `bg-${accentColor}-500/10`
          )}>
            <Icon className={cn("h-5 w-5", colorClasses[accentColor].split(" ").pop())} />
          </div>
          {change !== undefined && (
            <div className={cn(
              "flex items-center gap-1 text-xs font-medium",
              isPositive ? "text-emerald-400" : "text-red-400"
            )}>
              {isPositive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
              {isPositive ? "+" : ""}{change}%
            </div>
          )}
        </div>
        
        <p className="text-2xl font-semibold text-foreground mb-1">{value}</p>
        <p className="text-xs text-muted-foreground">{title}</p>
        
        {/* Mini sparkline */}
        {trend && (
          <div className="mt-3 h-8">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend.map((v, i) => ({ v }))}>
                <defs>
                  <linearGradient id={`spark-${accentColor}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={`var(--${accentColor}-500)`} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={`var(--${accentColor}-500)`} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={`oklch(0.65 0.18 ${accentColor === 'emerald' ? 145 : accentColor === 'amber' ? 75 : accentColor === 'red' ? 25 : 250})`}
                  strokeWidth={1.5}
                  fill={`url(#spark-${accentColor})`}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </motion.div>
  )
}

// AI Insight card
function InsightCard({ insight, onClick }: { insight: MetricInsight; onClick?: () => void }) {
  const router = useRouter()
  const config = {
    anomaly: { icon: AlertTriangle, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
    trend: { icon: TrendingUp, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
    optimization: { icon: Sparkles, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  }
  const cfg = config[insight.type as keyof typeof config]
  const Icon = cfg.icon
  const handleClick = () => {
    if (insight.relatedWorkflowId) {
      router.push(`/workflows/${insight.relatedWorkflowId}`)
    } else if (insight.relatedRunId) {
      router.push(`/runs?run=${insight.relatedRunId}`)
    } else if (insight.relatedConnectorId) {
      router.push(`/connectors/${insight.relatedConnectorId}`)
    }
    onClick?.()
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      onClick={handleClick}
      className={cn(
        "rounded-lg border p-3 transition-colors hover:bg-card/80 cursor-pointer",
        cfg.border, cfg.bg
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", cfg.bg)}>
          <Icon className={cn("h-4 w-4", cfg.color)} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground mb-0.5">{insight.title}</p>
          <p className="text-xs text-muted-foreground line-clamp-2">{insight.description}</p>
          <p className="text-[10px] text-muted-foreground mt-1">{insight.timestamp}</p>
        </div>
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" tabIndex={-1} aria-hidden="true">
          <Eye className="h-3.5 w-3.5" />
        </Button>
      </div>
    </motion.div>
  )
}

// Custom tooltip with glow effect
function GlowTooltip({ active, payload, label }: { active?: boolean; payload?: unknown[]; label?: string }) {
  if (!active || !payload?.length) return null
  
  return (
    <div className="rounded-lg border border-border bg-card/95 backdrop-blur-sm px-3 py-2 shadow-lg">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      {(payload as { name: string; value: number; color: string }[]).map((entry, i) => (
        <p key={i} className="text-xs font-medium" style={{ color: entry.color }}>
          {entry.name}: {entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  )
}

const timeRangeOptions = [
  { value: "1h", label: "Last hour" },
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
]

export default function MetricsPage() {
  const { user } = useAuth()
  const [timeRange, setTimeRange] = useState("24h")
  const [isExporting, setIsExporting] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const handleExport = async () => {
    setIsExporting(true)
    try {
      const response = await apiFetch(`/api/metrics/export?range=${timeRange}&format=csv`)
      if (!response.ok) throw new Error("Export failed")
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `gravitre-metrics-${timeRange}-${new Date().toISOString().split("T")[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success("Metrics exported successfully")
    } catch (err) {
      console.error("[v0] Export failed:", err)
      toast.error("Failed to export metrics")
    } finally {
      setIsExporting(false)
    }
  }

  const handleRefresh = () => {
    void mutateOverview()
    void mutateSeries()
    void mutateInsights()
    void mutateThroughput()
    toast.success("Metrics refreshed")
  }
  
  const { data: overviewData, isLoading, isValidating, mutate: mutateOverview } = useSWR<unknown>(
    user ? ["metrics-overview", timeRange] : null,
    () => metricsApi.overview(timeRange),
    {
      revalidateOnFocus: false,
      refreshInterval: autoRefresh ? 15000 : 0,
      onError: (err) => console.error("[v0] Metrics fetch error:", err),
    }
  )
  const { data: seriesData, mutate: mutateSeries } = useSWR(
    user ? ["metrics-runs", timeRange] : null,
    () => metricsApi.runs(timeRange),
    {
      revalidateOnFocus: false,
      refreshInterval: autoRefresh ? 15000 : 0,
    }
  )
  const { data: insightsData, mutate: mutateInsights } = useSWR(
    user ? ["metrics-insights", timeRange] : null,
    () => metricsApi.insights(timeRange),
    {
      revalidateOnFocus: false,
      refreshInterval: autoRefresh ? 60000 : 0,
    }
  )
  const { data: throughputDataRaw, mutate: mutateThroughput } = useSWR(
    user ? "metrics-weekly-throughput" : null,
    () => metricsApi.weeklyThroughput(),
    {
      revalidateOnFocus: false,
      refreshInterval: autoRefresh ? 60000 : 0,
    }
  )

  const overview = normalizeOverview(overviewData)
  const series = normalizeSeries(seriesData)
  const insights = normalizeInsights(insightsData)
  const runData = series.runVolume
  const latencyData = series.latencyDistribution
  const latencySpikeTime = series.latencySpikeTime
  const { days: throughputData, target: throughputTarget } = normalizeWeeklyThroughput(throughputDataRaw)

  return (
    <AppShell title={SURFACE_COPY.pages.metrics.title}>
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex-shrink-0 px-4 md:px-6 pt-4 md:pt-6 pb-4 border-b border-border">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between mb-4">
            <div>
              <h1 className="text-lg md:text-xl font-semibold text-foreground">{SURFACE_COPY.pages.metrics.headline}</h1>
              <p className="text-xs md:text-sm text-muted-foreground mt-1">{SURFACE_COPY.pages.metrics.description}</p>
            </div>
            <div className="flex items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 gap-2">
                    <Calendar className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Last</span> {timeRangeOptions.find(o => o.value === timeRange)?.label.replace("Last ", "") || "24h"}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {timeRangeOptions.map((option) => (
                    <DropdownMenuItem 
                      key={option.value}
                      onSelect={() => {
                        setTimeRange(option.value)
                        toast.success(`Showing ${option.label.toLowerCase()}`)
                      }}
                      className="gap-2"
                    >
                      {option.label}
                      {timeRange === option.value && <Check className="h-3.5 w-3.5 ml-auto" />}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 w-8 p-0 md:w-auto md:px-3 md:gap-2" 
                onClick={handleRefresh}
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading || isValidating ? "animate-spin" : ""}`} />
              </Button>
              <Button
                variant={autoRefresh ? "default" : "outline"}
                size="sm"
                className="h-8 gap-2"
                onClick={() => setAutoRefresh(!autoRefresh)}
              >
                <Activity className={`h-3.5 w-3.5 ${autoRefresh ? "animate-pulse" : ""}`} />
                <span className="hidden sm:inline">{autoRefresh ? "Live" : "Paused"}</span>
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                className="h-8 gap-2"
                onClick={handleExport}
                disabled={isExporting}
              >
                <Download className={`h-3.5 w-3.5 ${isExporting ? "animate-pulse" : ""}`} />
                <span className="hidden sm:inline">{isExporting ? "Exporting..." : "Export"}</span>
              </Button>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          <div className="p-4 md:p-6 space-y-4 md:space-y-6">
            {/* Top Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4">
              <MetricCard
                title="Total Runs"
                value={overview.totalRuns.toLocaleString()}
                change={overview.changes?.totalRuns}
                trend={overview.trends?.totalRuns}
                icon={Activity}
                accentColor="blue"
              />
              <MetricCard
                title="Success Rate"
                value={`${overview.successRate.toFixed(1)}%`}
                change={overview.changes?.successRate}
                trend={overview.trends?.successRate}
                icon={CheckCircle2}
                accentColor="emerald"
              />
              <MetricCard
                title="Records Processed"
                value={formatRecordsCount(overview.recordsProcessed)}
                change={overview.changes?.recordsProcessed}
                trend={overview.trends?.recordsProcessed}
                icon={Zap}
                accentColor="blue"
              />
              <MetricCard
                title="Avg Latency"
                value={`${Math.round(overview.avgLatency)}ms`}
                change={overview.changes?.avgLatency}
                trend={overview.trends?.avgLatency}
                icon={Clock}
                accentColor={overview.changes?.avgLatency && overview.changes.avgLatency > 0 ? "amber" : "emerald"}
              />
              <MetricCard
                title="Active Connectors"
                value={`${overview.activeConnectors}/${overview.totalConnectors}`}
                icon={Activity}
                accentColor="blue"
              />
            </div>

            {/* Main Charts + Meson Insights */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
              {/* Run Volume Chart */}
              <div className="lg:col-span-2 rounded-xl border border-border bg-card overflow-hidden">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <h3 className="text-sm font-medium text-foreground">Execution Volume</h3>
                  <div className="flex items-center gap-4 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-emerald-500" />
                      <span className="text-muted-foreground">Completed</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-red-500" />
                      <span className="text-muted-foreground">Failed</span>
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <ResponsiveContainer width="100%" height={240}>
                    <AreaChart data={runData}>
                      <defs>
                        <linearGradient id="colorCompleted" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="oklch(0.65 0.18 145)" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="oklch(0.65 0.18 145)" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorFailed" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="oklch(0.55 0.22 25)" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="oklch(0.55 0.22 25)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.20 0.01 250)" vertical={false} />
                      <XAxis dataKey="time" tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<GlowTooltip />} />
                      <Area
                        type="monotone"
                        dataKey="completed"
                        name="Completed"
                        stroke="oklch(0.65 0.18 145)"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorCompleted)"
                      />
                      <Area
                        type="monotone"
                        dataKey="failed"
                        name="Failed"
                        stroke="oklch(0.55 0.22 25)"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#colorFailed)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Meson Insights Panel */}
              <div className="rounded-xl border border-border bg-gradient-to-br from-card to-primary/5 overflow-hidden">
                <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-primary" />
                  <h3 className="text-sm font-medium text-foreground">Meson Insights</h3>
                </div>
                <div className="p-3 space-y-2 max-h-[280px] overflow-auto">
                  {insights.map((insight) => (
                    <InsightCard key={insight.id} insight={insight} />
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              {/* Latency Chart with anomaly markers */}
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <h3 className="text-sm font-medium text-foreground">Latency Distribution</h3>
                  {latencySpikeTime ? (
                    <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10">
                      <AlertTriangle className="h-3 w-3 text-amber-400" />
                      <span className="text-[10px] font-medium text-amber-400">
                        Spike detected at {latencySpikeTime}
                      </span>
                    </div>
                  ) : latencyData.length === 0 ? (
                    <span className="text-[10px] text-muted-foreground">No latency samples in range</span>
                  ) : null}
                </div>
                <div className="p-4">
                  <ResponsiveContainer width="100%" height={200}>
                    <LineChart data={latencyData}>
                      <defs>
                        <linearGradient id="latencyGlow" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="oklch(0.65 0.2 250)" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.20 0.01 250)" vertical={false} />
                      <XAxis dataKey="time" tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<GlowTooltip />} />
                      {latencySpikeTime ? (
                        <ReferenceLine x={latencySpikeTime} stroke="oklch(0.75 0.15 75)" strokeDasharray="3 3" />
                      ) : null}
                      <Line type="monotone" dataKey="p50" name="P50" stroke="oklch(0.65 0.2 250)" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="p95" name="P95" stroke="oklch(0.75 0.15 75)" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="p99" name="P99" stroke="oklch(0.55 0.22 25)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                  <div className="flex items-center justify-center gap-6 mt-3">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-primary" />
                      <span className="text-xs text-muted-foreground">P50</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-warning" />
                      <span className="text-xs text-muted-foreground">P95</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-destructive" />
                      <span className="text-xs text-muted-foreground">P99</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Throughput with target line */}
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="px-4 py-3 border-b border-border">
                  <h3 className="text-sm font-medium text-foreground">Weekly Throughput</h3>
                </div>
                <div className="p-4">
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={throughputData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.20 0.01 250)" vertical={false} />
                      <XAxis dataKey="day" tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "oklch(0.60 0 0)", fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                      <Tooltip content={<GlowTooltip />} />
                      {throughputTarget > 0 && (
                        <ReferenceLine
                          y={throughputTarget}
                          stroke="oklch(0.65 0.18 145)"
                          strokeDasharray="5 5"
                          label={{
                            value: "Target",
                            fill: "oklch(0.65 0.18 145)",
                            fontSize: 10,
                            position: "right",
                          }}
                        />
                      )}
                      <Bar 
                        dataKey="records" 
                        name="Records"
                        fill="oklch(0.65 0.2 250)" 
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
