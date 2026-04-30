"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { 
  TrendingUp, 
  TrendingDown, 
  Activity,
  GitBranch,
  CheckCircle2,
  XCircle,
  Clock,
  BarChart3
} from "lucide-react"

interface MetricCard {
  label: string
  value: number
  suffix?: string
  trend: number
  trendUp: boolean
}

const INITIAL_METRICS: MetricCard[] = [
  { label: "Total Workflows", value: 47, trend: 12, trendUp: true },
  { label: "Success Rate", value: 96.2, suffix: "%", trend: 2.1, trendUp: true },
  { label: "Avg Duration", value: 1.8, suffix: "s", trend: 0.3, trendUp: false },
  { label: "Runs Today", value: 234, trend: 18, trendUp: true },
]

const WORKFLOW_DATA = [
  { name: "Lead Sync", runs: 89, success: 87, avgTime: 1.2 },
  { name: "Email Campaign", runs: 56, success: 54, avgTime: 2.1 },
  { name: "Data Backup", runs: 48, success: 48, avgTime: 0.8 },
  { name: "Report Gen", runs: 41, success: 39, avgTime: 3.2 },
]

const CHART_DATA = [
  { day: "Mon", completed: 45, failed: 2 },
  { day: "Tue", completed: 52, failed: 3 },
  { day: "Wed", completed: 38, failed: 1 },
  { day: "Thu", completed: 61, failed: 4 },
  { day: "Fri", completed: 55, failed: 2 },
  { day: "Sat", completed: 28, failed: 0 },
  { day: "Sun", completed: 22, failed: 1 },
]

function MiniChart({ data }: { data: typeof CHART_DATA }) {
  const maxValue = Math.max(...data.map((d) => d.completed + d.failed))
  
  return (
    <div className="flex items-end gap-1 h-16">
      {data.map((item, index) => (
        <div key={item.day} className="flex-1 flex flex-col gap-0.5">
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: `${(item.completed / maxValue) * 100}%` }}
            transition={{ delay: index * 0.1, duration: 0.5 }}
            className="bg-emerald-500 rounded-t-sm w-full"
          />
          {item.failed > 0 && (
            <motion.div
              initial={{ height: 0 }}
              animate={{ height: `${(item.failed / maxValue) * 100}%` }}
              transition={{ delay: index * 0.1 + 0.2, duration: 0.3 }}
              className="bg-red-400 rounded-b-sm w-full"
            />
          )}
        </div>
      ))}
    </div>
  )
}

export function MetricsDemo() {
  const [metrics, setMetrics] = useState(INITIAL_METRICS)
  const [timeRange, setTimeRange] = useState<"7d" | "30d" | "90d">("7d")
  const [isLive, setIsLive] = useState(true)

  // Simulate live updates
  useEffect(() => {
    if (!isLive) return

    const interval = setInterval(() => {
      setMetrics((prev) =>
        prev.map((metric) => ({
          ...metric,
          value:
            metric.suffix === "%"
              ? Math.min(100, metric.value + (Math.random() - 0.4) * 0.5)
              : metric.suffix === "s"
              ? Math.max(0.5, metric.value + (Math.random() - 0.5) * 0.2)
              : Math.round(metric.value + (Math.random() - 0.3) * 3),
        }))
      )
    }, 3000)

    return () => clearInterval(interval)
  }, [isLive])

  return (
    <div className="relative rounded-xl border border-border bg-background overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-blue-100 flex items-center justify-center">
            <BarChart3 className="h-4 w-4 text-blue-600" />
          </div>
          <span className="font-medium text-sm text-foreground">Metrics Dashboard</span>
          {isLive && (
            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-xs">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 p-0.5 rounded-lg bg-muted">
          {(["7d", "30d", "90d"] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${
                timeRange === range
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {metrics.map((metric, index) => (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className="p-3 rounded-lg border border-border bg-background"
            >
              <div className="text-xs text-muted-foreground mb-1">{metric.label}</div>
              <div className="flex items-baseline gap-1">
                <span className="text-xl font-semibold text-foreground">
                  {metric.suffix === "%" 
                    ? metric.value.toFixed(1) 
                    : metric.suffix === "s"
                    ? metric.value.toFixed(1)
                    : Math.round(metric.value)}
                </span>
                {metric.suffix && (
                  <span className="text-sm text-muted-foreground">{metric.suffix}</span>
                )}
              </div>
              <div className={`flex items-center gap-0.5 text-xs mt-1 ${
                metric.trendUp ? "text-emerald-600" : "text-amber-600"
              }`}>
                {metric.trendUp ? (
                  <TrendingUp className="h-3 w-3" />
                ) : (
                  <TrendingDown className="h-3 w-3" />
                )}
                <span>{metric.trend}%</span>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Chart */}
        <div className="rounded-lg border border-border p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-foreground">Workflow Runs</span>
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Completed
              </span>
              <span className="flex items-center gap-1 text-muted-foreground">
                <span className="h-2 w-2 rounded-full bg-red-400" />
                Failed
              </span>
            </div>
          </div>
          <MiniChart data={CHART_DATA} />
          <div className="flex justify-between mt-2">
            {CHART_DATA.map((item) => (
              <span key={item.day} className="text-[10px] text-muted-foreground">
                {item.day}
              </span>
            ))}
          </div>
        </div>

        {/* Workflow Table */}
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="px-3 py-2 bg-muted/30 border-b border-border">
            <span className="text-xs font-medium text-foreground">Top Workflows</span>
          </div>
          <div className="divide-y divide-border">
            {WORKFLOW_DATA.map((workflow) => (
              <div
                key={workflow.name}
                className="flex items-center justify-between px-3 py-2 hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-sm text-foreground">{workflow.name}</span>
                </div>
                <div className="flex items-center gap-4 text-xs">
                  <span className="text-muted-foreground">{workflow.runs} runs</span>
                  <span className="flex items-center gap-1 text-emerald-600">
                    <CheckCircle2 className="h-3 w-3" />
                    {Math.round((workflow.success / workflow.runs) * 100)}%
                  </span>
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {workflow.avgTime}s
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
