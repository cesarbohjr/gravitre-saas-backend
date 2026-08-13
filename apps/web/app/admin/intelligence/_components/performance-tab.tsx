"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import {
  AlertTriangle,
  Clock,
  Coins,
  Gauge,
  Sparkles,
  Timer,
  Zap,
} from "lucide-react"
import { Label } from "@/components/ui/label"
import { ErrorState } from "@/components/gravitre/empty-state"
import { AnimatedMetricBar } from "@/components/gravitre/animated-metric-bar"
import { CHART_EMERALD, CHART_TEAL, cacheHitBarClass } from "@/components/gravitre/chart-brand"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { formatPercent, readNumber } from "./shared"

type PerformanceMode = "speed_priority" | "balanced" | "accuracy_priority"

const MODE_OPTIONS: { value: PerformanceMode; label: string; hint: string }[] = [
  {
    value: "speed_priority",
    label: "Speed priority",
    hint: "Faster replies via stronger caching; deeper checks only on advanced modes.",
  },
  {
    value: "balanced",
    label: "Balanced",
    hint: "Default blend of speed and source checks for everyday work.",
  },
  {
    value: "accuracy_priority",
    label: "Accuracy priority",
    hint: "Full search and validation on every answer — slower, more careful.",
  },
]

const PERIODS = ["1h", "24h", "7d"] as const

function StageTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value?: number; payload?: { p95Ms?: number } }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  const avg = readNumber(payload[0]?.value)
  const p95 = readNumber(payload[0]?.payload?.p95Ms)
  return (
    <div className="rounded-lg border border-border/70 bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium capitalize text-foreground">{label}</p>
      <p className="mt-1 text-muted-foreground">
        Avg <span className="font-semibold tabular-nums text-emerald-600 dark:text-emerald-400">{avg} ms</span>
      </p>
      {p95 > 0 ? (
        <p className="text-muted-foreground">
          P95 <span className="font-semibold tabular-nums text-foreground">{p95} ms</span>
        </p>
      ) : null}
    </div>
  )
}

export function PerformanceTab({ enabled }: { enabled: boolean }) {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>("24h")
  const [mode, setMode] = useState<PerformanceMode>("balanced")
  const [savingMode, setSavingMode] = useState(false)

  const { data: modeData, mutate: mutateMode } = useSWR(
    enabled ? "admin/intelligence/performance-mode" : null,
    () => intelligenceApi.performanceMode(),
    { revalidateOnFocus: false },
  )

  const {
    data: dashboard,
    error,
    isLoading,
    mutate,
  } = useSWR(enabled ? ["admin/intelligence/performance", period] : null, () =>
    intelligenceApi.performance({ period }),
  )

  useEffect(() => {
    if (modeData?.mode) {
      setMode(modeData.mode as PerformanceMode)
    }
  }, [modeData?.mode])

  const stageChart = useMemo(() => {
    const byStage = dashboard?.byStage ?? {}
    return Object.entries(byStage).map(([stage, stats]) => ({
      stage: stage.replace(/_/g, " "),
      avgMs: readNumber((stats as { avgMs?: number }).avgMs),
      p95Ms: readNumber((stats as { p95Ms?: number }).p95Ms),
    }))
  }, [dashboard?.byStage])

  const cacheEntries = useMemo(() => {
    return Object.entries(dashboard?.cacheHitRate ?? {}).map(([key, rate]) => ({
      key,
      label: key.replace(/_/g, " "),
      rate: readNumber(rate),
      pct: Math.round(readNumber(rate) * 100),
    }))
  }, [dashboard?.cacheHitRate])

  const maxStageMs = useMemo(
    () => Math.max(...stageChart.map((row) => row.avgMs), 1),
    [stageChart],
  )

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load performance metrics."
    return <ErrorState title="Unable to load performance" description={message} onRetry={() => mutate()} />
  }

  const saveMode = async (next: PerformanceMode) => {
    setSavingMode(true)
    try {
      await intelligenceApi.updatePerformanceMode({ mode: next })
      setMode(next)
      toast.success("Performance mode updated")
      await mutateMode()
    } catch (saveError) {
      toast.error(saveError instanceof ApiError ? saveError.message : "Could not save performance mode")
    } finally {
      setSavingMode(false)
    }
  }

  return (
    <div className="space-y-6">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-card via-card/95 to-emerald-500/[0.05] p-5 shadow-sm"
      >
        <div aria-hidden className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-emerald-500/10 blur-2xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 ring-1 ring-emerald-500/20">
              <Gauge className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </span>
            <div>
              <h3 className="text-base font-semibold text-foreground">Speed vs carefulness</h3>
              <p className="mt-0.5 max-w-xl text-xs text-muted-foreground text-pretty">
                Choose how aggressively Gravitre caches fast answers versus how often it re-checks sources.
              </p>
            </div>
          </div>
        </div>
        <div className="relative mt-4 grid gap-3 sm:grid-cols-3">
          {MODE_OPTIONS.map((option, index) => (
            <motion.button
              key={option.value}
              type="button"
              disabled={savingMode}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
              onClick={() => void saveMode(option.value)}
              className={cn(
                "rounded-xl border p-4 text-left transition-all",
                mode === option.value
                  ? "border-emerald-500/40 bg-emerald-500/10 shadow-sm ring-1 ring-emerald-500/20"
                  : "border-border/70 bg-background/50 hover:border-emerald-500/25 hover:bg-background/80",
              )}
            >
              <p className="text-sm font-medium text-foreground">{option.label}</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{option.hint}</p>
            </motion.button>
          ))}
        </div>
      </motion.section>

      <div className="flex flex-wrap items-center gap-2">
        <Label className="sr-only">Period</Label>
        <div className="flex items-center gap-0.5 rounded-lg border border-border/70 bg-secondary/30 p-1">
          {PERIODS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setPeriod(value)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                period === value
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {isLoading || !dashboard ? (
        <div className="flex items-center gap-2 rounded-xl border border-dashed border-border/70 bg-card/40 px-4 py-8 text-sm text-muted-foreground">
          <Sparkles className="h-4 w-4 animate-pulse text-emerald-500" />
          Loading performance metrics…
        </div>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiTile
              icon={Clock}
              tone="emerald"
              label="Avg response"
              value={`${readNumber(dashboard.avgTotalResponseMs)} ms`}
              delay={0}
            />
            <KpiTile
              icon={Timer}
              tone="sky"
              label="Slow responses (P95)"
              value={`${readNumber(dashboard.p95TotalResponseMs)} ms`}
              delay={0.05}
            />
            <KpiTile
              icon={Coins}
              tone="teal"
              label="Avg cost / answer"
              value={`$${readNumber(dashboard.avgCostPerAnswerUsd).toFixed(4)}`}
              delay={0.1}
            />
            <KpiTile
              icon={AlertTriangle}
              tone="amber"
              label="Timeout rate"
              value={formatPercent(readNumber(dashboard.timeoutRate))}
              delay={0.15}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="rounded-xl border border-border/60 bg-background/40 p-4 ring-1 ring-border/40"
            >
              <p className="mb-1 text-sm font-medium text-foreground">Where time is spent</p>
              <p className="mb-3 text-xs text-muted-foreground">Average milliseconds per step in the selected period</p>
              <div className="h-64">
                {stageChart.length === 0 ? (
                  <p className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No pipeline samples in this period.
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stageChart} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="stageBarGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={CHART_EMERALD} stopOpacity={0.95} />
                          <stop offset="100%" stopColor={CHART_TEAL} stopOpacity={0.65} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                      <XAxis
                        dataKey="stage"
                        tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip content={<StageTooltip />} cursor={{ fill: "var(--muted)", opacity: 0.15 }} />
                      <Bar
                        dataKey="avgMs"
                        fill="url(#stageBarGradient)"
                        radius={[6, 6, 0, 0]}
                        isAnimationActive
                        animationDuration={800}
                        animationEasing="ease-out"
                      >
                        {stageChart.map((entry) => (
                          <Cell
                            key={entry.stage}
                            fillOpacity={0.55 + (entry.avgMs / maxStageMs) * 0.45}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.16 }}
              className="rounded-xl border border-border/60 bg-background/40 p-4 ring-1 ring-border/40"
            >
              <div className="mb-3 flex items-center gap-2">
                <Zap className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="text-sm font-medium text-foreground">Cache hit rates</p>
                  <p className="text-xs text-muted-foreground">How often fast paths reuse prior work</p>
                </div>
              </div>
              {cacheEntries.length === 0 ? (
                <p className="text-sm text-muted-foreground">No cache telemetry in this period.</p>
              ) : (
                <ul className="space-y-1">
                  {cacheEntries.map((entry, index) => (
                    <AnimatedMetricBar
                      key={entry.key}
                      label={entry.label}
                      value={entry.pct}
                      displayValue={formatPercent(entry.rate)}
                      index={index}
                      barClassName={cacheHitBarClass(entry.rate)}
                    />
                  ))}
                </ul>
              )}
            </motion.div>
          </div>
        </>
      )}
    </div>
  )
}

function KpiTile({
  icon: Icon,
  tone,
  label,
  value,
  delay,
}: {
  icon: typeof Clock
  tone: "emerald" | "sky" | "teal" | "amber"
  label: string
  value: string
  delay: number
}) {
  const toneStyles = {
    emerald: "border-emerald-500/20 bg-emerald-500/5",
    sky: "border-sky-500/20 bg-sky-500/5",
    teal: "border-teal-500/20 bg-teal-500/5",
    amber: "border-amber-500/20 bg-amber-500/5",
  }
  const iconStyles = {
    emerald: "text-emerald-600 dark:text-emerald-400",
    sky: "text-sky-600 dark:text-sky-400",
    teal: "text-teal-600 dark:text-teal-400",
    amber: "text-amber-600 dark:text-amber-400",
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className={cn("rounded-xl border p-4 shadow-sm", toneStyles[tone])}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("h-4 w-4", iconStyles[tone])} />
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
    </motion.div>
  )
}
