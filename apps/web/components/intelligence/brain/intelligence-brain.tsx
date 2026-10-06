"use client"

import { useId, useMemo, useState } from "react"
import Link from "next/link"
import { motion, useReducedMotion } from "framer-motion"
import { ArrowRight, Pause, Play } from "lucide-react"
import { APP_ROUTES } from "@/lib/app-routes"
import type { IntelligencePageContextResponse } from "@/lib/api"
import {
  buildBrainModel,
  buildExampleBrainModel,
  type BrainCurvePoint,
  type BrainLogEntry,
  type BrainMetric,
  type BrainModel,
  type BrainTone,
} from "@/lib/intelligence/brain-model"
import { BrainNetworkCanvas, brainLayerX } from "@/components/intelligence/brain/brain-network-canvas"
import { cn } from "@/lib/utils"

const TONE_TEXT: Record<BrainTone, string> = {
  neutral: "text-[color:var(--g-text-primary)]",
  intelligence: "text-[color:var(--g-intelligence)]",
  brand: "text-[color:var(--g-brand-active,var(--g-brand))] dark:text-[color:var(--g-brand)]",
  approval: "text-[color:var(--g-approval)]",
  danger: "text-[color:var(--g-danger)]",
}

const TONE_VAR: Record<BrainTone, string> = {
  neutral: "var(--g-text-muted)",
  intelligence: "var(--g-intelligence)",
  brand: "var(--g-brand)",
  approval: "var(--g-approval)",
  danger: "var(--g-danger)",
}

const CONFIDENCE_TONES: BrainTone[] = ["brand", "intelligence", "approval", "neutral"]

const LOG_LABEL: Record<BrainLogEntry["tag"], string> = {
  LEARNED: "Learned",
  FORECAST: "Forecast",
  OUTCOME: "Outcome",
  INFO: "Update",
}

const LOG_TONE: Record<BrainLogEntry["tag"], BrainTone> = {
  LEARNED: "approval",
  FORECAST: "intelligence",
  OUTCOME: "brand",
  INFO: "neutral",
}

const CORE_STATE_LABEL: Record<string, { label: string; tone: BrainTone }> = {
  active: { label: "Active", tone: "brand" },
  learning: { label: "Learning", tone: "approval" },
  running: { label: "Running", tone: "brand" },
  idle: { label: "Idle", tone: "neutral" },
  degraded: { label: "Degraded", tone: "danger" },
}

const SPEEDS = [
  { value: 0.5, label: "0.5×" },
  { value: 1, label: "1×" },
  { value: 2, label: "2×" },
]

const panel = "rounded-[var(--np-radius-md)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]"
const panelTitle = "text-xs font-medium text-[color:var(--g-text-secondary)]"

function relativeTime(at: string | null, now: number): string {
  const ms = Date.parse(at ?? "")
  if (!Number.isFinite(ms)) return "—"
  const minutes = Math.max(0, Math.round((now - ms) / 60_000))
  if (minutes < 1) return "now"
  if (minutes < 60) return `${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `${hours}h`
  return `${Math.round(hours / 24)}d`
}

function updatedLabel(at: string | null): string {
  const ago = relativeTime(at, Date.now())
  if (ago === "—") return "not updated yet"
  return ago === "now" ? "updated just now" : `updated ${ago} ago`
}

function Sparkline({ series, tone }: { series: number[]; tone: BrainTone }) {
  const gradientId = useId()
  if (series.length < 2) {
    return <div className="h-6 border-b border-dashed border-[color:var(--g-border-subtle)]" aria-hidden />
  }
  const min = Math.min(...series)
  const max = Math.max(...series)
  const range = max - min || 1
  const pts = series.map((v, i) => [(i / (series.length - 1)) * 100, 22 - ((v - min) / range) * 18] as const)
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ")
  return (
    <svg viewBox="0 0 100 24" preserveAspectRatio="none" className="h-6 w-full" aria-hidden>
      <defs>
        <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" style={{ stopColor: TONE_VAR[tone], stopOpacity: 0.22 }} />
          <stop offset="1" style={{ stopColor: TONE_VAR[tone], stopOpacity: 0 }} />
        </linearGradient>
      </defs>
      <path d={`${line} L100,24 L0,24 Z`} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" style={{ stroke: TONE_VAR[tone] }} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function MetricCard({ metric }: { metric: BrainMetric }) {
  return (
    <div className="border-b border-[color:var(--g-border-subtle)] px-4 py-3 last:border-b-0">
      <p className={panelTitle}>{metric.label}</p>
      <p className={cn("mt-1 font-mono text-xl font-semibold tabular-nums leading-tight", TONE_TEXT[metric.tone])}>
        {metric.value}
      </p>
      <p className="mt-0.5 truncate text-[11px] text-[color:var(--g-text-muted)]">{metric.sub}</p>
      <div className="mt-2">
        <Sparkline series={metric.series} tone={metric.tone} />
      </div>
    </div>
  )
}

function LayerBars({ model }: { model: BrainModel }) {
  const max = Math.max(1, ...model.layers.map((l) => l.count ?? 0))
  return (
    <div className="px-4 py-3">
      <p className={panelTitle}>Signal per layer</p>
      <ul className="mt-2 space-y-1.5">
        {model.layers.map((layer) => {
          const share = layer.count ? Math.max(0.04, Math.log(layer.count + 1) / Math.log(max + 1)) : 0
          return (
            <li key={layer.id} className="grid grid-cols-[4.5rem_1fr_2.75rem] items-center gap-2 text-[11px]">
              <span className="truncate text-[color:var(--g-text-secondary)]">{layer.label}</span>
              <span className="h-1.5 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]">
                <motion.span
                  className="block h-full rounded-full"
                  style={{ background: TONE_VAR[layer.tone] }}
                  initial={{ width: 0 }}
                  animate={{ width: `${share * 100}%` }}
                  transition={{ duration: 0.8, ease: "easeOut" }}
                />
              </span>
              <span className="text-right font-mono tabular-nums text-[color:var(--g-text-muted)]">
                {layer.count == null ? "—" : layer.count.toLocaleString("en-US")}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function ConfidencePanel({ model }: { model: BrainModel }) {
  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between">
        <p className={panelTitle}>Forecast confidence</p>
        <Link
          href={APP_ROUTES.intelligencePredictive}
          className="text-[11px] font-medium text-[color:var(--g-text-muted)] hover:text-foreground"
        >
          All
        </Link>
      </div>
      {model.confidence.length === 0 ? (
        <p className="mt-2 text-xs text-[color:var(--g-text-muted)]">
          No scored forecasts yet. They appear once a model has enough outcomes to predict from.
        </p>
      ) : (
        <ul className="mt-2 space-y-2.5">
          {model.confidence.map((item, i) => {
            const tone = CONFIDENCE_TONES[i % CONFIDENCE_TONES.length]
            return (
              <li key={item.id}>
                <div className="flex items-baseline justify-between gap-2">
                  <span className="line-clamp-1 text-xs text-[color:var(--g-text-primary)]" title={item.label}>
                    {item.label}
                  </span>
                  <span className={cn("font-mono text-[11px] tabular-nums", TONE_TEXT[tone])}>
                    {(item.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <span className="mt-1 block h-1 overflow-hidden rounded-full bg-[color:var(--g-surface-2)]">
                  <motion.span
                    className="block h-full rounded-full"
                    style={{ background: TONE_VAR[tone] }}
                    initial={{ width: 0 }}
                    animate={{ width: `${item.confidence * 100}%` }}
                    transition={{ duration: 0.8, ease: "easeOut", delay: i * 0.08 }}
                  />
                </span>
                {item.detail ? (
                  <span className="mt-0.5 block text-[10px] text-[color:var(--g-text-muted)]">{item.detail}</span>
                ) : null}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function LearningLog({ model, now }: { model: BrainModel; now: number }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col px-4 py-3">
      <div className="flex items-center justify-between">
        <p className={panelTitle}>Learning log</p>
        <Link
          href={APP_ROUTES.learning}
          className="text-[11px] font-medium text-[color:var(--g-text-muted)] hover:text-foreground"
        >
          All
        </Link>
      </div>
      {model.log.length === 0 ? (
        <p className="mt-2 text-xs text-[color:var(--g-text-muted)]">
          Nothing new in this window. Learnings, forecasts, and outcomes show up here as they happen.
        </p>
      ) : (
        <ol className="mt-2 min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1" aria-label="Recent changes">
          {model.log.map((entry, i) => (
            <motion.li
              key={entry.id}
              className="grid grid-cols-[2.25rem_3.75rem_1fr] gap-1.5 text-[11px] leading-snug"
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: Math.min(i, 8) * 0.05 }}
            >
              <span className="font-mono tabular-nums text-[color:var(--g-text-muted)]">{relativeTime(entry.at, now)}</span>
              <span className={cn("font-medium", TONE_TEXT[LOG_TONE[entry.tag]])}>{LOG_LABEL[entry.tag]}</span>
              <span className="line-clamp-2 text-[color:var(--g-text-secondary)]">{entry.message}</span>
            </motion.li>
          ))}
        </ol>
      )}
    </div>
  )
}

function OutcomeCurve({ points, reduced }: { points: BrainCurvePoint[]; reduced: boolean }) {
  const strokeId = useId()
  const fillId = useId()
  const clipId = useId()
  if (points.length < 2) {
    return (
      <div className="flex h-[88px] items-center justify-center rounded-[var(--np-radius-sm,4px)] border border-dashed border-[color:var(--g-border-subtle)] text-xs text-[color:var(--g-text-muted)]">
        The curve starts once two or more outcomes carry a confidence score.
      </div>
    )
  }
  const values = points.map((p) => p.value)
  const min = Math.max(0, Math.min(...values) - 0.05)
  const max = Math.min(1, Math.max(...values) + 0.05)
  const range = max - min || 1
  const t0 = Date.parse(points[0].at)
  const t1 = Date.parse(points[points.length - 1].at)
  const span = t1 - t0 || 1
  const pts = points.map((p) => [((Date.parse(p.at) - t0) / span) * 100, 34 - ((p.value - min) / range) * 30] as const)
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ")
  const [hx, hy] = pts[pts.length - 1]
  const last = values[values.length - 1]
  return (
    <div className="relative">
      <svg viewBox="0 0 100 36" preserveAspectRatio="none" className="h-[88px] w-full overflow-visible" role="img" aria-label={`Outcome confidence moved from ${(values[0] * 100).toFixed(0)}% to ${(last * 100).toFixed(0)}% across ${points.length} outcomes`}>
        <defs>
          <linearGradient id={strokeId} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" style={{ stopColor: "var(--g-danger)", stopOpacity: 0.6 }} />
            <stop offset="0.5" style={{ stopColor: "var(--g-approval)", stopOpacity: 0.8 }} />
            <stop offset="1" style={{ stopColor: "var(--g-brand)" }} />
          </linearGradient>
          <linearGradient id={fillId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" style={{ stopColor: "var(--g-intelligence)", stopOpacity: 0.14 }} />
            <stop offset="1" style={{ stopColor: "var(--g-intelligence)", stopOpacity: 0 }} />
          </linearGradient>
          <clipPath id={clipId}>
            <motion.rect
              x="0"
              y="-4"
              height="44"
              initial={reduced ? false : { width: 0 }}
              animate={{ width: 100 }}
              transition={{ duration: 1.4, ease: "easeOut" }}
            />
          </clipPath>
        </defs>
        {[9, 18, 27].map((y) => (
          <line key={y} x1="0" x2="100" y1={y} y2={y} style={{ stroke: "var(--g-border-subtle)" }} strokeWidth={0.5} vectorEffect="non-scaling-stroke" />
        ))}
        <g clipPath={`url(#${clipId})`}>
          <path d={`${line} L${hx},36 L0,36 Z`} fill={`url(#${fillId})`} />
          <path d={line} fill="none" stroke={`url(#${strokeId})`} strokeWidth={2} vectorEffect="non-scaling-stroke" />
        </g>
      </svg>
      <span
        className="pointer-events-none absolute h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[color:var(--g-brand)] shadow-[0_0_8px_var(--g-brand)]"
        style={{ left: `${hx}%`, top: `${(hy / 36) * 100}%` }}
        aria-hidden
      />
    </div>
  )
}

/**
 * Intelligence overview: the org drawn as a layered network with its live
 * metrics around it. Real data by default; example data only on request and
 * always badged.
 */
export function IntelligenceBrain({
  pageContext,
  loading,
  className,
}: {
  pageContext?: IntelligencePageContextResponse | null
  loading?: boolean
  className?: string
}) {
  const prefersReduced = useReducedMotion() ?? false
  const [paused, setPaused] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [example, setExample] = useState<BrainModel | null>(null)
  const real = useMemo(() => buildBrainModel(pageContext), [pageContext])
  const model = example ?? real
  const now = Date.parse(model.generatedAt ?? "") || Date.now()
  const state = CORE_STATE_LABEL[model.coreState] ?? { label: loading ? "Loading" : "Unknown", tone: "neutral" as BrainTone }
  const totalNodes = model.layers.reduce((sum, l) => sum + l.nodes, 0)

  return (
    <section
      aria-labelledby="intelligence-brain-heading"
      data-testid="intelligence-brain"
      data-example={model.example ? "true" : "false"}
      className={cn("space-y-3", className)}
    >
      <div className={cn(panel, "flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5")}>
        <h2 id="intelligence-brain-heading" className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <span className="relative flex h-2 w-2" aria-hidden>
            {!paused && !prefersReduced ? (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-60" style={{ background: TONE_VAR[state.tone] }} />
            ) : null}
            <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: TONE_VAR[state.tone] }} />
          </span>
          Intelligence core
        </h2>
        <span
          className={cn("rounded-full border px-2 py-0.5 text-[11px] font-medium", TONE_TEXT[state.tone])}
          style={{ borderColor: `color-mix(in srgb, ${TONE_VAR[state.tone]} 40%, transparent)` }}
        >
          {state.label}
        </span>
        <span className="font-mono text-[11px] text-[color:var(--g-text-muted)]">
          Last {model.windowHours ?? "—"}h · {updatedLabel(model.generatedAt)}
        </span>
        {model.example ? (
          <span className="rounded-full bg-[color:var(--g-approval)]/15 px-2 py-0.5 text-[11px] font-medium text-[color:var(--g-approval)]">
            Example data
          </span>
        ) : null}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {model.example ? (
            <button
              type="button"
              onClick={() => setExample(null)}
              className="h-7 rounded-md px-2 text-[11px] font-medium text-[color:var(--g-text-secondary)] hover:bg-[color:var(--g-surface-2)] hover:text-foreground"
            >
              Show my data
            </button>
          ) : real.sparse && !loading ? (
            <button
              type="button"
              onClick={() => setExample(buildExampleBrainModel())}
              className="h-7 rounded-md px-2 text-[11px] font-medium text-[color:var(--g-text-secondary)] hover:bg-[color:var(--g-surface-2)] hover:text-foreground"
            >
              Preview with example data
            </button>
          ) : null}
          <div className="flex items-center overflow-hidden rounded-md border border-[color:var(--g-border-subtle)]" role="group" aria-label="Animation speed">
            {SPEEDS.map((s) => (
              <button
                key={s.value}
                type="button"
                aria-pressed={speed === s.value}
                disabled={prefersReduced}
                onClick={() => setSpeed(s.value)}
                className={cn(
                  "h-7 px-2 font-mono text-[11px] transition-colors disabled:opacity-40",
                  speed === s.value
                    ? "bg-[color:var(--g-surface-2)] text-foreground"
                    : "text-[color:var(--g-text-muted)] hover:text-foreground",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            disabled={prefersReduced}
            aria-pressed={paused}
            className="inline-flex h-7 items-center gap-1 rounded-md border border-[color:var(--g-border-subtle)] px-2 text-[11px] font-medium text-[color:var(--g-text-secondary)] hover:text-foreground disabled:opacity-40"
          >
            {paused ? <Play className="h-3 w-3" /> : <Pause className="h-3 w-3" />}
            {paused ? "Resume" : "Pause"}
          </button>
        </div>
      </div>

      {model.example ? (
        <p className="rounded-[var(--np-radius-md)] border border-[color:var(--g-approval)]/30 bg-[color:var(--g-approval)]/10 px-4 py-2 text-xs text-[color:var(--g-text-secondary)]">
          This is example data to show what the overview looks like. Your own numbers fill in as Gravitre connects sources, learns, and records outcomes.
        </p>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)] xl:grid-cols-[232px_minmax(0,1fr)_264px]">
        <aside aria-label="Core metrics" className={cn(panel, "order-2 grid sm:grid-cols-2 lg:order-1 lg:block")}>
          {model.metrics.map((metric) => (
            <MetricCard key={metric.id} metric={metric} />
          ))}
          <div className="border-t border-[color:var(--g-border-subtle)] sm:col-span-2">
            <LayerBars model={model} />
          </div>
        </aside>

        <div className={cn(panel, "relative order-1 min-h-[420px] overflow-hidden bg-[color:var(--g-surface-2)]/40 lg:order-2 lg:min-h-[460px]")}>
          <BrainNetworkCanvas
            layers={model.layers}
            activity={model.activity}
            paused={paused}
            speed={speed}
            reducedMotion={prefersReduced}
            className="absolute inset-0"
          />
          <nav aria-label="Intelligence layers" className="pointer-events-none absolute inset-x-0 top-3">
            {model.layers.map((layer, i) => (
              <Link
                key={layer.id}
                href={layer.href}
                className="pointer-events-auto absolute w-[18%] -translate-x-1/2 rounded-md px-1 py-1 text-center transition-colors hover:bg-[color:var(--g-surface-1)]/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--g-brand)]"
                style={{ left: `${brainLayerX(i, model.layers.length)}%` }}
                title={`Open ${layer.label}`}
              >
                <span className={cn("block truncate text-[11px] font-semibold sm:text-xs", TONE_TEXT[layer.tone])}>
                  {layer.label}
                </span>
                <span className="mt-0.5 hidden truncate font-mono text-[10px] text-[color:var(--g-text-muted)] sm:block">
                  {layer.detail}
                </span>
              </Link>
            ))}
          </nav>
          <div className="pointer-events-none absolute inset-x-3 bottom-3 flex flex-wrap items-end justify-between gap-2">
            <ul className="flex flex-wrap gap-x-3 gap-y-1 rounded-md bg-[color:var(--g-surface-1)]/85 px-2.5 py-1.5 text-[10px] text-[color:var(--g-text-secondary)] backdrop-blur-sm" aria-label="Legend">
              <li className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-brand)]" aria-hidden />Signal flowing in</li>
              <li className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[color:var(--g-intelligence)]" aria-hidden />Feedback from outcomes</li>
              <li className="flex items-center gap-1.5"><span className="h-0.5 w-3 rounded-full bg-[color:var(--g-approval)]" aria-hidden />Learning applied</li>
            </ul>
            <span className="hidden rounded-md bg-[color:var(--g-surface-1)]/85 px-2.5 py-1.5 font-mono text-[10px] text-[color:var(--g-text-muted)] backdrop-blur-sm sm:inline">
              {model.layers.length} layers · {totalNodes} nodes{paused ? " · paused" : ""}
            </span>
          </div>
          <p className="sr-only">
            {model.layers.map((l) => `${l.label}: ${l.detail}.`).join(" ")}
          </p>
        </div>

        <aside aria-label="Forecasts and learning log" className={cn(panel, "order-3 flex flex-col divide-y divide-[color:var(--g-border-subtle)] lg:col-span-2 lg:grid lg:grid-cols-2 lg:divide-x lg:divide-y-0 xl:col-span-1 xl:flex xl:max-h-[520px] xl:divide-x-0 xl:divide-y")}>
          <ConfidencePanel model={model} />
          <LearningLog model={model} now={now} />
        </aside>
      </div>

      <div className={cn(panel, "px-4 py-3")}>
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <p className={panelTitle}>Outcome confidence over time</p>
          <div className="flex items-center gap-3 font-mono text-[10px] text-[color:var(--g-text-muted)]">
            <span>{model.curve.length} outcomes scored</span>
            <Link href={APP_ROUTES.intelligencePerformance} className="inline-flex items-center gap-1 font-sans text-[11px] font-medium text-[color:var(--g-text-secondary)] hover:text-foreground">
              See impact <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        </div>
        <OutcomeCurve points={model.curve} reduced={prefersReduced} />
      </div>
    </section>
  )
}
