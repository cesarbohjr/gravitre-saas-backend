"use client"

import { useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { fetcher as apiFetcher } from "@/lib/fetcher"
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

const fallbackRunData = [
  { time: "00:00", completed: 45, failed: 2, latency: 120 },
  { time: "04:00", completed: 32, failed: 1, latency: 110 },
  { time: "08:00", completed: 78, failed: 3, latency: 145 },
  { time: "12:00", completed: 124, failed: 5, latency: 180 },
  { time: "14:32", completed: 89, failed: 8, latency: 320, anomaly: true }, // Anomaly point
  { time: "16:00", completed: 156, failed: 4, latency: 165 },
  { time: "20:00", completed: 98, failed: 2, latency: 130 },
  { time: "Now", completed: 67, failed: 1, latency: 125 },
]

const fallbackLatencyData = [
  { time: "00:00", p50: 120, p95: 450, p99: 890 },
  { time: "04:00", p50: 110, p95: 420, p99: 780 },
  { time: "08:00", p50: 145, p95: 520, p99: 1020 },
  { time: "12:00", p50: 180, p95: 680, p99: 1340 },
  { time: "14:32", p50: 320, p95: 890, p99: 1800 }, // Spike
  { time: "16:00", p50: 165, p95: 590, p99: 1180 },
  { time: "20:00", p50: 130, p95: 480, p99: 920 },
  { time: "Now", p50: 125, p95: 460, p99: 880 },
]

const fallbackThroughputData = [
  { day: "Mon", records: 245000, target: 250000 },
  { day: "Tue", records: 312000, target: 250000 },
  { day: "Wed", records: 287000, target: 250000 },
  { day: "Thu", records: 356000, target: 250000 },
  { day: "Fri", records: 298000, target: 250000 },
  { day: "Sat", records: 145000, target: 250000 },
  { day: "Sun", records: 123000, target: 250000 },
]

const fallbackOverview = {
  totalRuns: 1247,
  successRate: 98.7,
  recordsProcessed: 1800000,
  avgLatency: 142,
  activeConnectors: 9,
  totalConnectors: 12,
  changes: {
    totalRuns: 12,
    successRate: 0.5,
    recordsProcessed: 24,
    avgLatency: -8,
  },
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

function normalizeOverview(payload: unknown): MetricsOverview {
  const fallback: MetricsOverview = fallbackOverview
  if (!payload || typeof payload !== "object") return fallback
  const model = payload as Record<string, unknown>
  return {
    totalRuns: parseNumber(model.totalRuns, fallback.totalRuns),
    successRate: parseNumber(model.successRate, fallback.successRate),
    recordsProcessed: parseNumber(model.recordsProcessed, fallback.recordsProcessed),
    avgLatency: parseNumber(model.avgLatency, fallback.avgLatency),
    activeConnectors: parseNumber(model.activeConnectors, fallback.activeConnectors),
    totalConnectors: parseNumber(model.totalConnectors, fallback.totalConnectors),
    changes: {
      totalRuns: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.totalRuns ?? model.totalRunsChange,
        fallback.changes.totalRuns
      ),
      successRate: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.successRate ?? model.successRateChange,
        fallback.changes.successRate
      ),
      recordsProcessed: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.recordsProcessed ??
          model.recordsProcessedChange,
        fallback.changes.recordsProcessed
      ),
      avgLatency: parseNumber(
        (model.changes as Record<string, unknown> | undefined)?.avgLatency ?? model.avgLatencyChange,
        fallback.changes.avgLatency
      ),
    },
  }
}

function normalizeSeries(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return {
      runVolume: fallbackRunData,
      latencyDistribution: fallbackLatencyData,
    }
  }
  const model = payload as Record<string, unknown>
  return {
    runVolume: Array.isArray(model.runVolume) ? model.runVolume : fallbackRunData,
    latencyDistribution: Array.isArray(model.latencyDistribution)
      ? model.latencyDistribution
      : fallbackLatencyData,
  }
}

// Meson Insights
const mesonInsights = [
  {
    id: "1",
    type: "anomaly",
    severity: "warning",
    title: "Latency spike detected at 14:32",
    description: "P50 latency increased 77% above baseline. Correlated with sync-customers workflow.",
    timestamp: "2 hours ago",
  },
  {
    id: "2",
    type: "trend",
    severity: "info",
    title: "Weekend throughput consistently lower",
    description: "Saturday/Sunday process 45% fewer records. Consider adjusting schedules.",
    timestamp: "Today",
  },
  {
    id: "3",
    type: "optimization",
    severity: "success",
    title: "etl-main-pipeline optimization available",
    description: "Parallelization could reduce avg duration by 35% based on resource analysis.",
    timestamp: "Today",
  },
]

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
function InsightCard({ insight }: { insight: typeof mesonInsights[0] }) {
  const config = {
    anomaly: { icon: AlertTriangle, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
    trend: { icon: TrendingUp, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20" },
    optimization: { icon: Sparkles, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
  }
  const cfg = config[insight.type as keyof typeof config]
  const Icon = cfg.icon

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "rounded-lg border p-3 transition-colors hover:bg-card/80",
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
        <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0">
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
  const [timeRange, setTimeRange] = useState("24h")
  const [isExporting, setIsExporting] = useState(false)

  const handleExport = () => {
    setIsExporting(true)
    // Simulate export
    setTimeout(() => {
      setIsExporting(false)
      // Create a mock CSV download
      const csvContent = `Time,Completed,Failed,Latency
00:00,45,2,120
04:00,32,1,110
08:00,78,3,145
12:00,124,5,180
14:32,89,8,320
16:00,156,4,165
20:00,98,2,130
Now,67,1,125`
      const blob = new Blob([csvContent], { type: "text/csv" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `metrics-${timeRange}-${new Date().toISOString().split("T")[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success("Metrics exported successfully")
    }, 800)
  }

  const handleRefresh = () => {
    mutate()
    toast.success("Metrics refreshed")
  }
  
  const { data: overviewData, isLoading, mutate } = useSWR(
    "/api/metrics/overview",
    apiFetcher,
    { fallbackData: fallbackOverview, revalidateOnFocus: false }
  )
  const { data: seriesData } = useSWR("/api/metrics/runs", apiFetcher, {
    fallbackData: { runVolume: fallbackRunData, latencyDistribution: fallbackLatencyData },
    revalidateOnFocus: false,
  })

  const overview = normalizeOverview(overviewData)
  const series = normalizeSeries(seriesData)
  const runData = series.runVolume
  const latencyData = series.latencyDistribution
  const throughputData = fallbackThroughputData

  return (
    <AppShell title="Metrics">
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="flex-shrink-0 px-4 md:px-6 pt-4 md:pt-6 pb-4 border-b border-border">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between mb-4">
            <div>
              <h1 className="text-lg md:text-xl font-semibold text-foreground">System Intelligence</h1>
              <p className="text-xs md:text-sm text-muted-foreground mt-1">AI-powered monitoring and insights</p>
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
                <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
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
                value={overview.totalRuns?.toLocaleString() ?? "1,247"}
                change={overview.changes?.totalRuns ?? 12}
                icon={Activity}
                accentColor="blue"
                trend={[45, 32, 78, 124, 89, 156, 98, 67]}
              />
              <MetricCard
                title="Success Rate"
                value={`${overview.successRate ?? 98.7}%`}
                change={overview.changes?.successRate ?? 0.5}
                icon={CheckCircle2}
                accentColor="emerald"
                trend={[98, 97, 99, 98, 96, 99, 98, 99]}
              />
              <MetricCard
                title="Records Processed"
                value={overview.recordsProcessed ? `${(overview.recordsProcessed / 1000000).toFixed(1)}M` : "1.8M"}
                change={overview.changes?.recordsProcessed ?? 24}
                icon={Zap}
                accentColor="blue"
                trend={[245, 312, 287, 356, 298, 145, 123, 267]}
              />
              <MetricCard
                title="Avg Latency"
                value={`${overview.avgLatency ?? 142}ms`}
                change={overview.changes?.avgLatency ?? -8}
                icon={Clock}
                accentColor={overview.changes?.avgLatency && overview.changes.avgLatency > 0 ? "amber" : "emerald"}
                trend={[120, 110, 145, 180, 320, 165, 130, 125]}
              />
              <MetricCard
                title="Active Connectors"
                value={`${overview.activeConnectors ?? 9}/${overview.totalConnectors ?? 12}`}
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
                  {mesonInsights.map((insight) => (
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
                  <div className="flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10">
                    <AlertTriangle className="h-3 w-3 text-amber-400" />
                    <span className="text-[10px] font-medium text-amber-400">Spike detected at 14:32</span>
                  </div>
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
                      {/* Anomaly reference area */}
                      <ReferenceLine x="14:32" stroke="oklch(0.75 0.15 75)" strokeDasharray="3 3" />
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
                      <ReferenceLine y={250000} stroke="oklch(0.65 0.18 145)" strokeDasharray="5 5" label={{ value: 'Target', fill: 'oklch(0.65 0.18 145)', fontSize: 10, position: 'right' }} />
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
