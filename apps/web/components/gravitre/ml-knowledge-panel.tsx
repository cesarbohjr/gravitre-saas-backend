"use client"

import { useMemo, useState } from "react"
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
} from "recharts"
import { cn } from "@/lib/utils"

// ---------------------------------------------------------------------------
// MOCK / SAMPLE DATA
// Replace `modelHealthMetrics` with a real API/data source (e.g. an aggregate
// from the model evaluation service) when one is available. Shape is intended
// to map 1:1 to a future `GET /api/models/health` style response.
// ---------------------------------------------------------------------------
const modelHealthMetrics = {
  // Weighted strengths, plain-language labels (no ML jargon). 0-100.
  dimensions: [
    { key: "accuracy", label: "Prediction Accuracy", value: 82 },
    { key: "learning", label: "Learning Speed", value: 68 },
    { key: "consistency", label: "Consistency", value: 76 },
    { key: "dataEfficiency", label: "Data Efficiency", value: 54 },
    { key: "adaptability", label: "Adaptability", value: 71 },
    { key: "resourceUsage", label: "Resource Usage", value: 63 },
    { key: "explainability", label: "Explainability", value: 47 },
  ],
  // Knowledge index over time, used by the Training Tendency sparkline.
  tendency: {
    30: [58, 60, 59, 62, 64, 63, 66, 68, 67, 70, 72, 73],
    60: [49, 52, 51, 55, 57, 56, 60, 62, 64, 67, 70, 73],
    90: [41, 44, 46, 45, 50, 53, 57, 59, 63, 66, 70, 73],
  },
  knowledgeGrowthPct: 12,
} as const

type RangeKey = keyof typeof modelHealthMetrics.tendency

const RANGES: RangeKey[] = [30, 60, 90]

// Green >= 75, amber 50-74, orange/red < 50 (mirrors the reference pattern).
// Explicit hex values: recharts SVG fill/stroke attributes do NOT resolve
// CSS custom properties (var(--x) falls back to black), so we pass real colors.
function bandColor(value: number): string {
  if (value >= 75) return "#10b981" // emerald-500 (green)
  if (value >= 50) return "#f59e0b" // amber-500
  return "#f97316" // orange-500
}

// Brand accents — purple primary (matches the registry hero + schedules page),
// with blue/green companions for the radar gradient.
const ACCENT = "#8b5cf6" // violet-500 / purple
const ACCENT_BLUE = "#3b82f6" // blue-500
const ACCENT_GREEN = "#10b981" // emerald-500

export function MlKnowledgePanel() {
  const [range, setRange] = useState<RangeKey>(30)

  const dims = modelHealthMetrics.dimensions
  const radarData = useMemo(
    () => dims.map((d) => ({ label: d.label, value: d.value })),
    [dims],
  )

  const { top, focus } = useMemo(() => {
    const sorted = [...dims].sort((a, b) => b.value - a.value)
    return { top: sorted[0], focus: sorted[sorted.length - 1] }
  }, [dims])

  const series = modelHealthMetrics.tendency[range]
  const trend = useMemo(() => {
    const delta = series[series.length - 1] - series[0]
    if (delta >= 8) return { label: "Improving steadily", icon: ArrowUpRight, tone: "up" as const }
    if (delta <= -4) return { label: "Needs attention", icon: ArrowDownRight, tone: "down" as const }
    return { label: "Plateauing", icon: ArrowRight, tone: "flat" as const }
  }, [series])

  const sparkData = series.map((v, i) => ({ i, v }))
  const TrendIcon = trend.icon

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className="rounded-2xl border border-border/70 bg-card/40 p-5 sm:p-6"
      aria-labelledby="ml-knowledge-heading"
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500/20 to-cyan-500/15 ring-1 ring-violet-500/20">
            <Gauge className="h-4 w-4 text-violet-400" />
          </span>
          <div>
            <h2 id="ml-knowledge-heading" className="text-base font-semibold text-foreground sm:text-lg">
              ML Knowledge &amp; Performance
            </h2>
            <p className="text-xs text-muted-foreground">
              Weighted model strengths and learning trend across your registry.
            </p>
          </div>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-background/60 px-2.5 py-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          <Sparkles className="h-3 w-3 text-violet-400" />
          Sample data
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        {/* Radar + dimension bars */}
        <div className="rounded-xl border border-border/60 bg-background/40 p-4">
          <p className="mb-1 text-sm font-medium text-foreground">Model Strengths Overview</p>
          <p className="mb-2 text-xs text-muted-foreground">Higher is better · 0–100 weighted score</p>
          <div className="h-[200px] w-full sm:h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={radarData} outerRadius="72%">
                <defs>
                  <radialGradient id="radarFill" cx="50%" cy="50%" r="65%">
                    <stop offset="0%" stopColor={ACCENT} stopOpacity={0.55} />
                    <stop offset="60%" stopColor={ACCENT_BLUE} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={ACCENT_GREEN} stopOpacity={0.12} />
                  </radialGradient>
                </defs>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis
                  dataKey="label"
                  tick={{ fill: "var(--muted-foreground)", fontSize: 10 }}
                />
                <Radar
                  dataKey="value"
                  stroke={ACCENT}
                  fill="url(#radarFill)"
                  fillOpacity={1}
                  strokeWidth={2}
                  dot={{ r: 3, fill: ACCENT, strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                  isAnimationActive
                  animationDuration={800}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <ul className="mt-3 space-y-2">
            {dims.map((d, i) => {
              const color = bandColor(d.value)
              return (
                <li
                  key={d.key}
                  className="flex items-center gap-3 rounded-md px-1.5 py-1 -mx-1.5 transition-colors hover:bg-muted/50"
                >
                  <span className="w-4 shrink-0 text-xs tabular-nums text-muted-foreground">{i + 1}</span>
                  <span className="w-24 shrink-0 truncate text-xs text-foreground sm:w-40">{d.label}</span>
                  <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-secondary/60">
                    <motion.span
                      className="absolute inset-y-0 left-0 rounded-full"
                      style={{ backgroundColor: color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${d.value}%` }}
                      transition={{ duration: 0.7, delay: 0.1 + i * 0.05, ease: "easeOut" }}
                    />
                  </span>
                  <span className="w-9 shrink-0 text-right text-xs font-medium tabular-nums text-foreground">
                    {d.value}%
                  </span>
                </li>
              )
            })}
          </ul>
        </div>

        {/* Training tendency + stat tiles */}
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
                        ? "bg-violet-500/15 text-violet-600 dark:text-violet-300"
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
                <AreaChart data={sparkData} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
                  <defs>
                    <linearGradient id="tendencyFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={ACCENT} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={ACCENT} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="v"
                    stroke={ACCENT}
                    strokeWidth={2}
                    fill="url(#tendencyFill)"
                    isAnimationActive
                    animationDuration={600}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div
              className={cn(
                "mt-1 inline-flex items-center gap-1.5 text-xs font-medium",
                trend.tone === "up" && "text-emerald-400",
                trend.tone === "down" && "text-orange-400",
                trend.tone === "flat" && "text-muted-foreground",
              )}
            >
              <TrendIcon className="h-3.5 w-3.5" />
              {trend.label}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            <StatTile
              icon={TrendingUp}
              tone="violet"
              label="Knowledge growth"
              value={`+${modelHealthMetrics.knowledgeGrowthPct}%`}
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
              label="Focus area"
              value={focus.label}
              hint={`${focus.value}%`}
            />
          </div>
        </div>
      </div>
    </motion.section>
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
  tone: "violet" | "emerald" | "amber"
  label: string
  value: string
  hint: string
}) {
  const toneStyles: Record<typeof tone, string> = {
    violet: "border-violet-500/20 bg-violet-500/5 text-violet-600 dark:text-violet-300",
    emerald: "border-emerald-500/20 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400",
    amber: "border-amber-500/20 bg-amber-500/5 text-amber-600 dark:text-amber-400",
  }
  return (
    <motion.div
      whileHover={{ y: -3 }}
      transition={{ type: "spring", stiffness: 320, damping: 22 }}
      className={cn(
        "rounded-xl border p-3 transition-shadow hover:shadow-md",
        toneStyles[tone],
      )}
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
