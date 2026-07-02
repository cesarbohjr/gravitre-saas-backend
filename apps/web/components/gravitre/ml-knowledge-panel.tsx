"use client"

import { useEffect, useMemo, useState } from "react"
import { motion } from "framer-motion"
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Gauge,
  Sparkles,
  Target,
  TrendingUp,
} from "lucide-react"
import {
  Area,
  AreaChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import type { DotProps } from "recharts"
import { AnimatedMetricBar } from "@/components/gravitre/animated-metric-bar"
import { CHART_EMERALD, CHART_TEAL, easeOutCubic } from "@/components/gravitre/chart-brand"
import type { ModelHealthDimension } from "@/lib/model-registry/mockData"
import { mockModelHealthMetrics } from "@/lib/model-registry/mockData"
import { cn } from "@/lib/utils"

type RangeKey = 30 | 60 | 90

const RANGES: RangeKey[] = [30, 60, 90]
const RADAR_GROW_MS = 1400
/** Uniform visual breathe — does not alter plotted scores. */
const RADAR_BREATHE = { scale: [1, 1.014, 1] as number[], opacity: [0.92, 1, 0.92] as number[] }

type RadarRow = { label: string; value: number; key: string }

function RadarValueDot({
  cx,
  cy,
  index,
  hoveredIndex,
  onHover,
}: DotProps & { index?: number; hoveredIndex: number | null; onHover: (index: number | null) => void }) {
  if (cx == null || cy == null || index == null) return null
  const active = hoveredIndex === index
  return (
    <circle
      cx={cx}
      cy={cy}
      r={active ? 6 : 3.5}
      fill={active ? "#fff" : CHART_EMERALD}
      stroke={CHART_EMERALD}
      strokeWidth={active ? 2.5 : 0}
      className="transition-[r,stroke-width] duration-200"
      onMouseEnter={() => onHover(index)}
      onMouseLeave={() => onHover(null)}
      style={{ cursor: "pointer" }}
    />
  )
}

function RadarDimensionTooltip({
  active,
  payload,
  dims,
  radarReady,
}: {
  active?: boolean
  payload?: Array<{ payload?: RadarRow; value?: number }>
  dims: ModelHealthDimension[]
  radarReady: boolean
}) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload
  if (!row) return null
  const source = dims.find((d) => d.key === row.key)
  const value = radarReady && source ? source.value : row.value

  return (
    <div className="rounded-lg border border-border/70 bg-card px-3 py-2 text-xs shadow-lg">
      <p className="font-medium text-foreground">{row.label}</p>
      <p className="mt-0.5 tabular-nums text-emerald-600 dark:text-emerald-400">
        <span className="text-lg font-semibold">{value}</span>
        <span className="text-muted-foreground"> / 100</span>
      </p>
    </div>
  )
}

function ModelStrengthsRadar({
  dims,
  animatedScores,
  radarReady,
  hoveredIndex,
  onHover,
}: {
  dims: ModelHealthDimension[]
  animatedScores: number[]
  radarReady: boolean
  hoveredIndex: number | null
  onHover: (index: number | null) => void
}) {
  const radarData: RadarRow[] = useMemo(
    () =>
      dims.map((d, i) => ({
        key: d.key,
        label: d.label,
        value: animatedScores[i] ?? 0,
      })),
    [dims, animatedScores],
  )

  return (
    <motion.div
      className="relative h-[200px] w-full sm:h-[240px]"
      initial={{ opacity: 0, scale: 0.94 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
    >
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-1/2 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500/10 blur-2xl"
        animate={{ scale: [0.92, 1.06, 0.92], opacity: [0.35, 0.65, 0.35] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="h-full w-full origin-center"
        animate={radarReady ? RADAR_BREATHE : { scale: 1, opacity: 1 }}
        transition={
          radarReady
            ? { duration: 5.5, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.3 }
        }
      >
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart
            data={radarData}
            outerRadius="72%"
            onMouseLeave={() => onHover(null)}
          >
            <defs>
              <radialGradient id="mlRadarFill" cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor={CHART_EMERALD} stopOpacity={0.55} />
                <stop offset="60%" stopColor={CHART_TEAL} stopOpacity={0.3} />
                <stop offset="100%" stopColor={CHART_EMERALD} stopOpacity={0.12} />
              </radialGradient>
            </defs>
            <PolarGrid stroke="var(--border)" strokeOpacity={0.8} />
            <PolarAngleAxis
              dataKey="label"
              tick={({ x, y, payload, textAnchor, ...rest }) => {
                const idx = dims.findIndex((d) => d.label === payload?.value)
                const active = hoveredIndex === idx
                return (
                  <text
                    {...rest}
                    x={x}
                    y={y}
                    textAnchor={textAnchor}
                    fill={active ? "var(--foreground)" : "var(--muted-foreground)"}
                    fontSize={10}
                    fontWeight={active ? 600 : 400}
                  >
                    {payload?.value}
                  </text>
                )
              }}
            />
            <Tooltip
              cursor={false}
              content={
                <RadarDimensionTooltip dims={dims} radarReady={radarReady} />
              }
            />
            <Radar
              dataKey="value"
              stroke={CHART_EMERALD}
              fill="url(#mlRadarFill)"
              fillOpacity={hoveredIndex != null ? 0.85 : 1}
              strokeWidth={hoveredIndex != null ? 2.5 : 2}
              isAnimationActive={!radarReady}
              animationDuration={600}
              animationEasing="ease-out"
              dot={(props) => (
                <RadarValueDot
                  {...props}
                  hoveredIndex={hoveredIndex}
                  onHover={onHover}
                />
              )}
              activeDot={false}
            />
          </RadarChart>
        </ResponsiveContainer>
      </motion.div>
      {!radarReady ? (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="pointer-events-none absolute bottom-1 left-0 right-0 text-center text-[10px] font-medium uppercase tracking-wider text-emerald-600/80 dark:text-emerald-400/80"
        >
          Calibrating strengths…
        </motion.p>
      ) : null}
    </motion.div>
  )
}

export function MlKnowledgePanel() {
  const [range, setRange] = useState<RangeKey>(30)
  const [radarReady, setRadarReady] = useState(false)
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const [animatedScores, setAnimatedScores] = useState<number[]>(() =>
    mockModelHealthMetrics.dimensions.map(() => 0),
  )

  const dims = mockModelHealthMetrics.dimensions

  useEffect(() => {
    setRadarReady(false)
    setHoveredIndex(null)
    setAnimatedScores(dims.map(() => 0))
    const start = performance.now()
    let raf = 0

    const tick = (now: number) => {
      const t = easeOutCubic((now - start) / RADAR_GROW_MS)
      if (t >= 1) {
        setAnimatedScores(dims.map((d) => d.value))
        setRadarReady(true)
        return
      }
      setAnimatedScores(dims.map((d) => Math.round(d.value * t)))
      raf = requestAnimationFrame(tick)
    }

    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [dims])

  const displayScores = useMemo(
    () => (radarReady ? dims.map((d) => d.value) : animatedScores),
    [dims, animatedScores, radarReady],
  )

  const { top, weakest } = useMemo(() => {
    const sorted = [...dims].sort((a, b) => b.value - a.value)
    return { top: sorted[0], weakest: sorted[sorted.length - 1] }
  }, [dims])

  const series = mockModelHealthMetrics.tendency[range]
  const trend = useMemo(() => {
    const delta = series[series.length - 1] - series[0]
    if (delta >= 8) return { label: "Improving steadily", icon: ArrowUpRight, tone: "up" as const }
    if (delta <= -4) return { label: "Needs attention", icon: ArrowDownRight, tone: "down" as const }
    return { label: "Plateauing", icon: ArrowRight, tone: "flat" as const }
  }, [series])

  const sparkData = series.map((v, i) => ({ i, v }))
  const TrendIcon = trend.icon

  return (
    <div
      className="rounded-xl border border-border/60 bg-background/50 p-4 ring-1 ring-border/40 backdrop-blur-sm"
      aria-labelledby="ml-knowledge-heading"
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-background/70 ring-1 ring-border/50">
            <Gauge className="h-4 w-4 text-emerald-600 dark:text-emerald-300" />
          </span>
          <div>
            <h3 id="ml-knowledge-heading" className="text-sm font-semibold text-foreground">
              ML Knowledge &amp; Performance
            </h3>
            <p className="text-xs text-muted-foreground">
              Weighted model strengths and learning trend across your registry.
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider text-emerald-600 dark:text-emerald-300">
          <motion.span
            animate={{ scale: [1, 1.25, 1], opacity: [0.6, 1, 0.6] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
            className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500"
          />
          <Sparkles className="h-3 w-3" />
          Sample data
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border border-border/60 bg-background/40 p-4">
          <p className="mb-1 text-sm font-medium text-foreground">Model Strengths Overview</p>
          <p className="mb-2 text-xs text-muted-foreground">Higher is better · 0–100 weighted score</p>

          <ModelStrengthsRadar
            dims={dims}
            animatedScores={displayScores}
            radarReady={radarReady}
            hoveredIndex={hoveredIndex}
            onHover={setHoveredIndex}
          />

          <ul className="mt-3 space-y-1">
            {dims.map((d, i) => (
              <AnimatedMetricBar
                key={d.key}
                label={d.label}
                value={displayScores[i] ?? 0}
                displayValue={`${displayScores[i] ?? 0}%`}
                index={i}
                highlighted={hoveredIndex === i}
                onHighlight={() => setHoveredIndex(i)}
                onUnhighlight={() => setHoveredIndex((current) => (current === i ? null : current))}
              />
            ))}
          </ul>
        </div>

        <div className="flex flex-col gap-4">
          <div className="rounded-xl border border-border/60 bg-background/40 p-4">
            <div className="mb-2 flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-foreground">Training Tendency</p>
              <div className="flex items-center gap-0.5 rounded-md border border-border/60 bg-background/60 p-0.5">
                {RANGES.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRange(r)}
                    className={cn(
                      "rounded px-1.5 py-0.5 text-[10px] font-medium transition-colors",
                      range === r
                        ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {r}d
                  </button>
                ))}
              </div>
            </div>
            <div className="h-[88px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={sparkData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} key={range}>
                  <defs>
                    <linearGradient id="mlTendencyFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_EMERALD} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={CHART_EMERALD} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="v"
                    stroke={CHART_EMERALD}
                    strokeWidth={2}
                    fill="url(#mlTendencyFill)"
                    isAnimationActive
                    animationDuration={700}
                    animationEasing="ease-out"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div
              className={cn(
                "mt-1 inline-flex items-center gap-1.5 text-xs font-medium",
                trend.tone === "up" && "text-emerald-600 dark:text-emerald-400",
                trend.tone === "down" && "text-orange-500 dark:text-orange-400",
                trend.tone === "flat" && "text-muted-foreground",
              )}
            >
              <TrendIcon className="h-3.5 w-3.5" />
              {trend.label}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <StatTile
              icon={TrendingUp}
              tone="teal"
              label="Knowledge growth"
              value={`+${mockModelHealthMetrics.knowledgeGrowthPct}%`}
              hint="this month"
            />
            <StatTile
              icon={Target}
              tone="emerald"
              label="Top strength"
              value={top.label}
              hint={`${top.value}%`}
            />
            <StatTile
              icon={Activity}
              tone="amber"
              label="Weakest area"
              value={weakest.label}
              hint={`${weakest.value}%`}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

function StatTile({
  icon: Icon,
  tone,
  label,
  value,
  hint,
}: {
  icon: typeof TrendingUp
  tone: "teal" | "emerald" | "amber"
  label: string
  value: string
  hint: string
}) {
  const toneStyles: Record<typeof tone, string> = {
    teal: "border-teal-500/20 bg-teal-500/5 text-teal-600 dark:text-teal-300",
    emerald: "border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400",
    amber: "border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400",
  }
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
      className={cn("rounded-lg border px-2.5 py-1.5", toneStyles[tone])}
    >
      <div className="flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" />
        <span className="text-[10px] font-medium uppercase tracking-wider opacity-90">{label}</span>
      </div>
      <p className="mt-1 truncate text-sm font-semibold text-foreground">{value}</p>
      <p className="text-[10px] text-muted-foreground">{hint}</p>
    </motion.div>
  )
}
