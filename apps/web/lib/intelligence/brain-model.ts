import type { IntelligencePageContextResponse } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { buildChangeEvents } from "@/lib/intelligence/build-change-events"

/**
 * The Intelligence overview draws the org as a layered network, the way an ML
 * training dashboard draws a model: what comes in (sources), what Gravitre
 * knows, what it learned, the models it runs, and the forecasts it makes.
 *
 * Every number here comes from the page-context snapshot. A value the backend
 * did not report stays null and renders as "—", never as zero. Animation speed
 * is the only thing derived for show, and it scales with real activity.
 */

export type BrainTone = "neutral" | "intelligence" | "brand" | "approval" | "danger"

export type BrainLayerId = "sources" | "knowledge" | "learning" | "models" | "forecasts"

export type BrainLayer = {
  id: BrainLayerId
  label: string
  /** Primary count for the layer; null when the backend did not report it. */
  count: number | null
  /** Short unit line under the label, e.g. "42 entities · 18 links". */
  detail: string
  /** Nodes drawn for the layer (3 to 12), scaled from count. */
  nodes: number
  tone: BrainTone
  href: string
}

export type BrainMetric = {
  id: string
  label: string
  value: string
  sub: string
  tone: BrainTone
  /** Real series only; fewer than 2 points means no sparkline. */
  series: number[]
}

export type BrainConfidence = {
  id: string
  label: string
  detail: string
  /** 0..1 */
  confidence: number
}

export type BrainLogEntry = {
  id: string
  at: string | null
  tag: "LEARNED" | "FORECAST" | "OUTCOME" | "INFO"
  message: string
}

export type BrainCurvePoint = { at: string; value: number }

export type BrainModel = {
  example: boolean
  coreState: string
  windowHours: number | null
  generatedAt: string | null
  layers: BrainLayer[]
  metrics: BrainMetric[]
  confidence: BrainConfidence[]
  log: BrainLogEntry[]
  /** Outcome confidence over the window, oldest first. */
  curve: BrainCurvePoint[]
  /** 0 (idle) .. 1 (busy): drives particle rate, nothing else. */
  activity: number
  /** True when there is too little data for the overview to say much. */
  sparse: boolean
}

type Snapshot = IntelligencePageContextResponse["snapshot"]

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null
}

/** 0..1 confidence from either a ratio or a percentage. */
function ratio(value: unknown): number | null {
  const n = num(value)
  if (n == null) return null
  const r = n > 1 ? n / 100 : n
  return Math.max(0, Math.min(1, r))
}

export function formatCount(value: number | null): string {
  if (value == null) return "—"
  if (Math.abs(value) >= 10_000) return `${(value / 1000).toFixed(value >= 100_000 ? 0 : 1)}k`
  return value.toLocaleString("en-US")
}

export function formatPercent(value: number | null): string {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`
}

/** Nodes drawn per layer grow with the log of the count so one big layer cannot crowd the rest. */
export function nodesForCount(count: number | null): number {
  if (count == null || count <= 0) return 3
  return Math.max(3, Math.min(12, Math.round(3 + Math.log2(count + 1) * 1.4)))
}

function plural(n: number | null, one: string, many = `${one}s`): string {
  return `${formatCount(n)} ${n === 1 ? one : many}`
}

function byTime(a: string | null, b: string | null): number {
  return (Date.parse(a ?? "") || 0) - (Date.parse(b ?? "") || 0)
}

/** Count events per bucket across the window so the sparkline shows rhythm, not totals. */
function bucketCounts(times: string[], buckets: number, end: number, windowMs: number): number[] {
  const start = end - windowMs
  const counts = new Array<number>(buckets).fill(0)
  for (const t of times) {
    const ms = Date.parse(t)
    if (!Number.isFinite(ms) || ms < start || ms > end) continue
    const i = Math.min(buckets - 1, Math.floor(((ms - start) / windowMs) * buckets))
    counts[i] += 1
  }
  return counts
}

const LOG_TAG: Record<string, BrainLogEntry["tag"]> = {
  learned: "LEARNED",
  prediction: "FORECAST",
  changed: "OUTCOME",
}

export function buildBrainModel(pageContext?: IntelligencePageContextResponse | null): BrainModel {
  const snap: Partial<Snapshot> = pageContext?.snapshot ?? {}
  const metrics = pageContext?.metrics ?? snap.metrics
  const knowledge = metrics?.knowledge ?? {}
  const learning = metrics?.learning ?? {}
  const predictionsM = metrics?.predictions ?? {}
  const execution = metrics?.execution ?? {}
  const outcomesM = metrics?.outcomes ?? {}

  const predictions = (snap.predictions ?? []) as Array<Record<string, unknown>>
  const learnings = (snap.learnings ?? []) as Array<Record<string, unknown>>
  const outcomes = (snap.outcomes ?? []) as Array<Record<string, unknown>>
  const models = (snap.models ?? []) as Array<Record<string, unknown>>
  const agents = snap.agents ?? []

  const sources =
    num(knowledge.knowledgeSources) || (snap.knowledgeEntityTypes?.length ?? null) || null
  const entities = num(knowledge.knownEntities)
  const relationships = num(knowledge.knownRelationships)
  const learningCount = num(learning.recentLearnings) ?? (pageContext ? learnings.length : null)
  const modelsTracked = num(learning.modelsTracked) ?? (models.length || null)
  const modelsImproved = num(learning.modelsImproved)
  const forecastCount = num(predictionsM.activePredictions) ?? (pageContext ? predictions.length : null)
  const highPriority = num(predictionsM.highPriorityPredictions)
  const running =
    num(execution.currentlyRunningAgents) ?? (agents.length ? agents.filter((a) => a.isCurrentlyRunning).length : null)
  const configured =
    num(execution.configuredActiveAgents) ?? (agents.length ? agents.filter((a) => a.isConfiguredActive).length : null)
  const awaiting = num(execution.awaitingApproval)
  const outcomeEvents = num(outcomesM.outcomeEventsInWindow) ?? (snap.outcomes ? outcomes.length : null)
  const measured = num(outcomesM.measuredOutcomes)

  const layers: BrainLayer[] = [
    {
      id: "sources",
      label: "Sources",
      count: sources,
      detail: plural(sources, "source"),
      nodes: nodesForCount(sources),
      tone: "neutral",
      href: APP_ROUTES.learning,
    },
    {
      id: "knowledge",
      label: "Knowledge",
      count: entities,
      detail: `${formatCount(entities)} entities · ${formatCount(relationships)} links`,
      nodes: nodesForCount(entities),
      tone: "intelligence",
      href: APP_ROUTES.learning,
    },
    {
      id: "learning",
      label: "Learning",
      count: learningCount,
      detail: plural(learningCount, "learning"),
      nodes: nodesForCount(learningCount),
      tone: "intelligence",
      href: APP_ROUTES.learning,
    },
    {
      id: "models",
      label: "Models",
      count: modelsTracked,
      detail: plural(modelsTracked, "model"),
      nodes: nodesForCount(modelsTracked),
      tone: "intelligence",
      href: APP_ROUTES.models,
    },
    {
      id: "forecasts",
      label: "Forecasts",
      count: forecastCount,
      detail: plural(forecastCount, "forecast"),
      nodes: nodesForCount(forecastCount),
      tone: "brand",
      href: APP_ROUTES.intelligencePredictive,
    },
  ]

  const end = Date.parse(snap.generatedAt ?? "") || Date.now()
  const windowHours = num(snap.timeWindowHours)
  const windowMs = (windowHours ?? 24) * 3_600_000
  const outcomeTimes = outcomes.map((o) => str(o.createdAt)).filter((t): t is string => Boolean(t))
  const outcomeSeries = outcomeTimes.length ? bucketCounts(outcomeTimes, 12, end, windowMs) : []

  const scoredForecasts = predictions
    .map((p) => ({ p, c: ratio(p.confidence) }))
    .filter((x): x is { p: Record<string, unknown>; c: number } => x.c != null)
  const avgForecast = scoredForecasts.length
    ? scoredForecasts.reduce((sum, x) => sum + x.c, 0) / scoredForecasts.length
    : null
  const forecastSeries = [...scoredForecasts]
    .sort((a, b) => byTime(str(a.p.createdAt), str(b.p.createdAt)))
    .map((x) => x.c * 100)

  const metricsOut: BrainMetric[] = [
    {
      id: "outcomes",
      label: "Outcome events",
      value: formatCount(outcomeEvents),
      sub: measured != null ? `${formatCount(measured)} measured` : `last ${windowHours ?? 24}h`,
      tone: "brand",
      series: outcomeSeries,
    },
    {
      id: "forecast-confidence",
      label: "Forecast confidence",
      value: formatPercent(avgForecast),
      sub: highPriority != null ? `${formatCount(highPriority)} high priority` : plural(forecastCount, "forecast"),
      tone: "intelligence",
      series: forecastSeries,
    },
    {
      id: "learnings",
      label: "Learnings",
      value: formatCount(learningCount),
      sub: modelsImproved != null ? `${formatCount(modelsImproved)} models improved` : "from your work",
      tone: "approval",
      series: [],
    },
    {
      id: "agents",
      label: "Agents running",
      value: running == null && configured == null ? "—" : `${formatCount(running)} / ${formatCount(configured)}`,
      sub: awaiting != null ? `${formatCount(awaiting)} awaiting approval` : "running / active",
      tone: "neutral",
      series: [],
    },
  ]

  const confidence: BrainConfidence[] = [...scoredForecasts]
    .sort((a, b) => b.c - a.c)
    .slice(0, 4)
    .map(({ p, c }) => ({
      id: String(p.id ?? p.semanticKey ?? p.businessStatement),
      label: String(p.subject ?? p.businessStatement ?? "Forecast"),
      detail: [str(p.department), str(p.horizon)].filter(Boolean).join(" · "),
      confidence: c,
    }))

  const learnedAt = new Map(learnings.map((l) => [`learning:${String(l.id ?? "")}`, str(l.learnedAt)]))
  const forecastAt = new Map(predictions.map((p) => [`prediction:${String(p.id ?? "")}`, str(p.createdAt)]))
  const log: BrainLogEntry[] = buildChangeEvents(pageContext)
    .map((e) => ({
      id: e.id,
      at: str(e.at) ?? learnedAt.get(e.id) ?? forecastAt.get(e.id) ?? null,
      tag: LOG_TAG[e.kind] ?? "INFO",
      message: e.title,
    }))
    .sort((a, b) => byTime(b.at, a.at))
    .slice(0, 12)

  const curve: BrainCurvePoint[] = outcomes
    .map((o) => ({ at: str(o.createdAt), value: ratio(o.confidence) }))
    .filter((p): p is BrainCurvePoint => p.at != null && p.value != null)
    .sort((a, b) => byTime(a.at, b.at))

  const busy = (running ?? 0) * 2 + (outcomeEvents ?? 0) / 4 + (learningCount ?? 0) / 3 + (forecastCount ?? 0) / 4
  const activity = Math.max(0, Math.min(1, busy / 12))

  const sparse =
    !predictions.length && !learnings.length && !outcomes.length && !(outcomeEvents ?? 0) && !(learningCount ?? 0)

  return {
    example: false,
    coreState: str(snap.coreState) ?? "unknown",
    windowHours,
    generatedAt: str(snap.generatedAt),
    layers,
    metrics: metricsOut,
    confidence,
    log,
    curve,
    activity,
    sparse,
  }
}

/**
 * Example data for orgs that have not connected enough yet. Shown only when the
 * person asks for a preview, always under an "Example data" badge.
 */
export function buildExampleBrainModel(now = Date.now()): BrainModel {
  const hoursAgo = (h: number) => new Date(now - h * 3_600_000).toISOString()
  const curveValues = [0.52, 0.55, 0.54, 0.59, 0.61, 0.6, 0.64, 0.67, 0.66, 0.7, 0.72, 0.71, 0.74, 0.76, 0.75, 0.78, 0.8, 0.79, 0.81, 0.83]
  const layer = (
    id: BrainLayerId,
    label: string,
    count: number,
    detail: string,
    tone: BrainTone,
    href: string,
  ): BrainLayer => ({ id, label, count, detail, nodes: nodesForCount(count), tone, href })
  return {
    example: true,
    coreState: "learning",
    windowHours: 24,
    generatedAt: new Date(now).toISOString(),
    layers: [
      layer("sources", "Sources", 6, "6 sources", "neutral", APP_ROUTES.learning),
      layer("knowledge", "Knowledge", 1284, "1,284 entities · 3,910 links", "intelligence", APP_ROUTES.learning),
      layer("learning", "Learning", 37, "37 learnings", "intelligence", APP_ROUTES.learning),
      layer("models", "Models", 5, "5 models", "intelligence", APP_ROUTES.models),
      layer("forecasts", "Forecasts", 14, "14 forecasts", "brand", APP_ROUTES.intelligencePredictive),
    ],
    metrics: [
      { id: "outcomes", label: "Outcome events", value: "212", sub: "48 measured", tone: "brand", series: [6, 9, 7, 12, 10, 15, 14, 18, 16, 21, 19, 24] },
      { id: "forecast-confidence", label: "Forecast confidence", value: "78.4%", sub: "6 high priority", tone: "intelligence", series: [61, 64, 63, 68, 70, 69, 73, 75, 74, 78] },
      { id: "learnings", label: "Learnings", value: "37", sub: "2 models improved", tone: "approval", series: [] },
      { id: "agents", label: "Agents running", value: "4 / 9", sub: "3 awaiting approval", tone: "neutral", series: [] },
    ],
    confidence: [
      { id: "ex-renew", label: "Acme renewal likely to expand", detail: "Sales · 30 days", confidence: 0.86 },
      { id: "ex-churn", label: "Two accounts at churn risk", detail: "Customer success · 14 days", confidence: 0.74 },
      { id: "ex-pipeline", label: "Q4 pipeline short of target", detail: "Revenue · this quarter", confidence: 0.68 },
      { id: "ex-tickets", label: "Support volume rising Monday", detail: "Support · 7 days", confidence: 0.57 },
    ],
    log: [
      { id: "ex-1", at: hoursAgo(0.2), tag: "LEARNED", message: "Deals with a technical call close 2× faster" },
      { id: "ex-2", at: hoursAgo(0.6), tag: "OUTCOME", message: "Renewal recovered for Northwind" },
      { id: "ex-3", at: hoursAgo(1.4), tag: "FORECAST", message: "Acme renewal likely to expand" },
      { id: "ex-4", at: hoursAgo(2.1), tag: "LEARNED", message: "Invoices sent Tuesday are paid sooner" },
      { id: "ex-5", at: hoursAgo(3.5), tag: "OUTCOME", message: "Lead triage routed 18 leads" },
      { id: "ex-6", at: hoursAgo(5.2), tag: "INFO", message: "Churn model retrained on new outcomes" },
      { id: "ex-7", at: hoursAgo(7.8), tag: "FORECAST", message: "Support volume rising Monday" },
    ],
    curve: curveValues.map((value, i) => ({ at: hoursAgo(24 - (i * 24) / curveValues.length), value })),
    activity: 0.75,
    sparse: false,
  }
}
