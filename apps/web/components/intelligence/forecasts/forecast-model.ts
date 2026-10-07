/**
 * Forecasts page model: merges the two real forecast sources into one list.
 *
 * 1. Intelligence page-context `snapshot.predictions` (canonical predictions
 *    deduped from business signals; see backend intelligence_prediction_dedup).
 * 2. Open workflow failure predictions (`GET /api/workflows/failure-predictions`),
 *    which carry a stable alert id, the connector / workflow involved and a
 *    dismiss endpoint. Business signals also echo these alerts (without ids),
 *    so a snapshot prediction whose title matches an open alert is dropped.
 *
 * Nothing here invents a value: unknown timing stays "No date yet", unknown
 * confidence stays null and renders as "—".
 */
import { formatVendorLabel } from "@/lib/connectors"
import type { WorkflowFailureAlert } from "@/types/api"

export type ForecastKind = "risk" | "opportunity" | "signal"
export type ForecastOrigin = "workflow_alert" | "prediction"

export type ForecastAction =
  | { type: "link"; label: string; href: string }
  | { type: "ask"; label: string; prompt: string }

export type Forecast = {
  /** Stable key: alert id, or the prediction's semantic key. */
  key: string
  origin: ForecastOrigin
  kind: ForecastKind
  title: string
  summary: string
  /** Department / area label in sentence case, or null when the source has none. */
  area: string | null
  confidence: number | null
  /** Days from now; 0 = next run / today; null = the source gave no timing. */
  horizonDays: number | null
  whenLabel: string
  drivers: string[]
  evidence: string[]
  /** True when this needs action before the next run. */
  needsYouNow: boolean
  /** True when the source flagged it as unscoped or it has no evidence. */
  needsEvidence: boolean
  action: ForecastAction
  evidenceHref: string
  confidenceNote: string
  /** Workflow failure alert id (dismiss endpoint), when origin is workflow_alert. */
  alertId?: string
}

export type FailureAlertWithEvidence = WorkflowFailureAlert & {
  evidence?: Record<string, unknown> | null
}

const WORKFLOWS_AREA = "Workflows"

function str(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

function strArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
}

export function sentenceCase(value: string): string {
  const text = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim().toLowerCase()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ""
}

export function normalizeTitle(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()
}

export function classifyKind(type: unknown): ForecastKind {
  const normalized = str(type).toLowerCase()
  if (normalized === "risk" || normalized === "alert") return "risk"
  if (normalized === "opportunity") return "opportunity"
  return "signal"
}

/**
 * Parse a horizon string ("7d", "2 weeks", "30 days", "next run", ISO date)
 * into days from `now`. Returns null when the value carries no timing.
 */
export function parseHorizonDays(horizon: unknown, now: number = Date.now()): number | null {
  if (typeof horizon === "number" && Number.isFinite(horizon)) return Math.max(0, horizon)
  const text = str(horizon).toLowerCase()
  if (!text) return null
  if (/next[\s_-]*run|today|now|immediate/.test(text)) return 0
  if (/tomorrow/.test(text)) return 1
  const match = text.match(/(\d+(?:\.\d+)?)\s*(h|hr|hour|d|day|w|wk|week|m|mo|month|q|quarter|y|yr|year)/)
  if (match) {
    const n = Number(match[1])
    const unit = match[2]
    if (unit.startsWith("h")) return n / 24
    if (unit === "d" || unit.startsWith("day")) return n
    if (unit.startsWith("w")) return n * 7
    if (unit === "m" || unit.startsWith("mo")) return n * 30
    if (unit.startsWith("q")) return n * 90
    if (unit.startsWith("y")) return n * 365
  }
  const parsed = Date.parse(text)
  if (Number.isFinite(parsed)) return Math.max(0, (parsed - now) / 86_400_000)
  return null
}

export function formatWhen(horizonDays: number | null, origin: ForecastOrigin): string {
  if (origin === "workflow_alert") return "Next run"
  if (horizonDays == null) return "No date yet"
  const days = Math.round(horizonDays)
  if (days <= 0) return "Today"
  if (days === 1) return "Tomorrow"
  if (days < 14) return `In ${days} days`
  if (days < 30) return `In ${Math.round(days / 7)} weeks`
  if (days < 60) return "In 1 month"
  return `In ${Math.round(days / 30)} months`
}

function formatExpiry(hours: number): string {
  if (hours < 1) return "Within the hour"
  if (hours < 36) return `In ${Math.round(hours)} hours`
  return formatWhen(hours / 24, "prediction")
}

export function confidenceLabel(confidence: number | null): string {
  if (confidence == null) return "Not scored"
  if (confidence < 0.6) return "Low"
  if (confidence < 0.7) return "Moderate"
  return "High"
}

export function formatPct(confidence: number | null): string {
  return confidence == null ? "—" : `${Math.round(confidence * 100)}%`
}

function normalizeConfidence(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null
  const n = Number(value)
  if (!Number.isFinite(n)) return null
  const scaled = n > 1 ? n / 100 : n
  return Math.max(0, Math.min(1, scaled))
}

function vendorFromAlert(alert: FailureAlertWithEvidence): string {
  const evidence = alert.evidence ?? {}
  const raw = str(evidence.connectorType) || str(evidence.connectorTypeRaw)
  if (raw) return formatVendorLabel(raw)
  const fromTitle = alert.title.replace(/\s+authentication required$/i, "").trim()
  return fromTitle && fromTitle !== alert.title ? formatVendorLabel(fromTitle) : "the connector"
}

/** Map one open workflow failure alert to a forecast. */
export function forecastFromFailureAlert(alert: FailureAlertWithEvidence): Forecast {
  const evidence = alert.evidence ?? {}
  const step = str(evidence.stepName)
  const stepLabel = step ? `The ${step} step` : "A workflow step"
  const workflowHref = alert.workflowId ? `/workflows/${alert.workflowId}/builder` : "/workflows"
  const confidence = normalizeConfidence(alert.confidence)
  const severity = alert.severity
  const needsYouNow = severity === "critical" || severity === "high"
  let expiryHours: number | null = null
  let title = alert.title
  let summary = alert.message
  let drivers: string[] = []
  let action: ForecastAction = { type: "link", label: "Open workflow", href: workflowHref }

  switch (alert.alertType) {
    case "auth_disconnected": {
      const vendor = vendorFromAlert(alert)
      title = `${vendor} sign-in needed`
      summary = `${stepLabel} will likely fail on its next run because ${vendor} is waiting to be reconnected.`
      drivers = [`The ${vendor} connector is waiting for sign-in`]
      if (step) drivers.push(`${step} reads ${vendor} when the workflow runs`)
      action = {
        type: "link",
        label: `Reconnect ${vendor}`,
        href: alert.connectorId ? `/connectors/${alert.connectorId}` : "/connectors",
      }
      break
    }
    case "auth_expiry": {
      const vendor = vendorFromAlert(alert)
      const hours = Number(evidence.hoursUntilExpiry)
      if (Number.isFinite(hours)) expiryHours = Math.max(0, hours)
      title = `${vendor} sign-in expiring`
      drivers = [
        Number.isFinite(hours)
          ? `The ${vendor} sign-in expires in about ${Math.max(0, Math.round(hours))} hours`
          : `The ${vendor} sign-in expires soon`,
      ]
      if (step) drivers.push(`${step} depends on ${vendor}`)
      action = {
        type: "link",
        label: `Reconnect ${vendor}`,
        href: alert.connectorId ? `/connectors/${alert.connectorId}` : "/connectors",
      }
      break
    }
    case "connector_missing": {
      const vendor = vendorFromAlert(alert)
      title = `${vendor} isn't connected`
      drivers = [`No active ${vendor} connector`]
      if (step) drivers.push(`${step} needs ${vendor}`)
      action = { type: "link", label: `Connect ${vendor}`, href: "/connectors" }
      break
    }
    case "missing_scope": {
      const agentId = str(evidence.agentId)
      drivers = ["An agent in this workflow lacks a tool permission"]
      if (str(evidence.action)) drivers.push(`It needs permission for ${str(evidence.action).replace(/[_.]+/g, " ")}`)
      action = agentId
        ? { type: "link", label: "Review agent permissions", href: `/agents/${agentId}` }
        : { type: "link", label: "Open workflow", href: workflowHref }
      break
    }
    case "step_failure_risk": {
      const failures = Number(evidence.recentFailures)
      const attempts = Number(evidence.recentAttempts)
      drivers =
        Number.isFinite(failures) && Number.isFinite(attempts)
          ? [`Failed in ${failures} of the last ${attempts} runs`]
          : ["This step has been failing in recent runs"]
      break
    }
    case "rate_limit_trend": {
      drivers = ["Rate-limit failures are rising compared with last week"]
      break
    }
    default:
      drivers = []
  }

  return {
    key: `alert:${alert.id}`,
    origin: "workflow_alert",
    kind: "risk",
    title,
    summary,
    area: WORKFLOWS_AREA,
    confidence,
    // Sign-in expiry has a real date; every other workflow alert is about the next run.
    horizonDays: expiryHours != null ? expiryHours / 24 : 0,
    whenLabel: expiryHours != null ? formatExpiry(expiryHours) : "Next run",
    drivers,
    evidence: alert.message ? [alert.message] : [],
    needsYouNow,
    needsEvidence: false,
    action,
    evidenceHref: "/activity?tab=failures",
    confidenceNote:
      confidence == null
        ? "Not scored yet."
        : `Estimated from how serious the problem is (${severity}). It sharpens as you mark how forecasts like this turn out.`,
    alertId: alert.id,
  }
}

/** Map one canonical snapshot prediction to a forecast. */
export function forecastFromPrediction(row: Record<string, unknown>, now: number = Date.now()): Forecast {
  const statement = str(row.businessStatement)
  const subject = str(row.subject)
  const objective = str(row.objective)
  const evidence = strArray(row.evidence)
  const qualityFlags = strArray(row.qualityFlags)
  const actions = strArray(row.recommendedActions)
  const department = str(row.department)
  const sourceModel = str(row.sourceModel)
  const horizonDays = parseHorizonDays(row.horizon, now)
  const confidence = normalizeConfidence(row.confidence)
  const title = subject || statement || "Business forecast"
  let summary = statement
  if (subject && statement.toLowerCase().startsWith(`${subject.toLowerCase()}:`)) {
    summary = statement.slice(subject.length + 1).trim()
  }
  if (!summary || summary === title) summary = evidence[0] && evidence[0] !== title ? evidence[0] : ""

  const drivers: string[] = []
  if (objective) drivers.push(objective)
  if (sourceModel) drivers.push(`Model: ${sourceModel}`)
  if (department) drivers.push(`Seen in ${sentenceCase(department).toLowerCase()} data`)

  const key = str(row.semanticKey) || str(row.id) || normalizeTitle(title).slice(0, 48)
  const recommended = actions[0]
  const action: ForecastAction = recommended
    ? {
        type: "ask",
        label: recommended,
        prompt: `Help me act on this forecast: "${title}". The recommended next step is: ${recommended}. Show me what you would do before changing anything.`,
      }
    : {
        type: "ask",
        label: "Ask what to do",
        prompt: `Gravitre forecasts: "${statement || title}". What should I do about it, and what evidence is it based on?`,
      }

  return {
    key: `prediction:${key}`,
    origin: "prediction",
    kind: classifyKind(row.type),
    title,
    summary,
    area: department ? sentenceCase(department) : null,
    confidence,
    horizonDays,
    whenLabel: formatWhen(horizonDays, "prediction"),
    drivers,
    evidence,
    needsYouNow: false,
    needsEvidence: qualityFlags.includes("UNSCOPED_PREDICTION") || evidence.length === 0,
    action,
    evidenceHref: "/intelligence/reports",
    confidenceNote:
      confidence == null
        ? "The source didn't give a confidence, so this isn't scored yet."
        : "Scored by the signal that raised it. It sharpens as you mark how forecasts like this turn out.",
  }
}

const KIND_ORDER: Record<ForecastKind, number> = { risk: 0, opportunity: 1, signal: 2 }

export function sortForecasts(rows: Forecast[]): Forecast[] {
  return [...rows].sort((a, b) => {
    if (a.needsYouNow !== b.needsYouNow) return a.needsYouNow ? -1 : 1
    if (a.kind !== b.kind) return KIND_ORDER[a.kind] - KIND_ORDER[b.kind]
    const ah = a.horizonDays ?? Number.POSITIVE_INFINITY
    const bh = b.horizonDays ?? Number.POSITIVE_INFINITY
    if (ah !== bh) return ah - bh
    return (b.confidence ?? -1) - (a.confidence ?? -1)
  })
}

/** Merge snapshot predictions with open workflow failure alerts. */
export function buildForecasts({
  predictions,
  failureAlerts,
  now = Date.now(),
}: {
  predictions?: Array<Record<string, unknown>> | null
  failureAlerts?: FailureAlertWithEvidence[] | null
  now?: number
}): Forecast[] {
  const alerts = (failureAlerts ?? []).filter((alert) => !alert.status || alert.status === "open")
  const alertTitles = new Set(alerts.map((alert) => normalizeTitle(alert.title)))
  const out: Forecast[] = alerts.map(forecastFromFailureAlert)
  const seen = new Set(out.map((row) => row.key))
  for (const row of predictions ?? []) {
    const forecast = forecastFromPrediction(row, now)
    if (alertTitles.has(normalizeTitle(forecast.title))) continue
    if (seen.has(forecast.key)) continue
    seen.add(forecast.key)
    out.push(forecast)
  }
  return sortForecasts(out)
}

export type ForecastSummary = {
  active: number
  risks: number
  opportunities: number
  signals: number
  needYouNow: number
  needEvidence: number
}

export function summarizeForecasts(rows: Forecast[]): ForecastSummary {
  return {
    active: rows.length,
    risks: rows.filter((row) => row.kind === "risk").length,
    opportunities: rows.filter((row) => row.kind === "opportunity").length,
    signals: rows.filter((row) => row.kind === "signal").length,
    needYouNow: rows.filter((row) => row.needsYouNow).length,
    needEvidence: rows.filter((row) => row.needsEvidence).length,
  }
}

/** Area chips: "All departments" plus every area present, in first-seen order. */
export function forecastAreas(rows: Forecast[]): string[] {
  const areas: string[] = []
  for (const row of rows) {
    if (row.area && !areas.includes(row.area)) areas.push(row.area)
  }
  return areas
}

// ---------------------------------------------------------------------------
// Timeline layout
// ---------------------------------------------------------------------------

/** Tick positions (% of plot width). */
export const TIMELINE_TICKS = [
  { label: "Today", days: 0, x: 0 },
  { label: "2 weeks", days: 14, x: 24 },
  { label: "1 month", days: 30, x: 48 },
  { label: "2 months +", days: 60, x: 72 },
] as const

export const UNDATED_X = 90

export function horizonToX(horizonDays: number | null): number {
  if (horizonDays == null) return UNDATED_X
  const d = Math.max(0, horizonDays)
  for (let i = 1; i < TIMELINE_TICKS.length; i += 1) {
    const prev = TIMELINE_TICKS[i - 1]
    const next = TIMELINE_TICKS[i]
    if (d <= next.days) {
      return prev.x + ((d - prev.days) / (next.days - prev.days)) * (next.x - prev.x)
    }
  }
  // Beyond 60 days: ease toward the end of the dated range without passing it.
  return Math.min(82, 72 + ((d - 60) / 120) * 10)
}

export type TimelineDot = {
  forecast: Forecast
  x: number
  lane: number
  side: "above" | "below"
  size: number
}

/** Dot diameter in px: bigger dot, more confident. */
export function dotSize(confidence: number | null): number {
  if (confidence == null) return 8
  return Math.round(Math.max(8, Math.min(22, 8 + (confidence - 0.5) * 40)))
}

/**
 * Risks above the line, opportunities below. Signals (neither) are listed but
 * not plotted. Chips that would overlap move to the next of three lanes.
 */
export function layoutTimeline(rows: Forecast[], lanes = 3, minGap = 22): TimelineDot[] {
  const dots: TimelineDot[] = []
  for (const side of ["above", "below"] as const) {
    const kind: ForecastKind = side === "above" ? "risk" : "opportunity"
    const placed = rows
      .filter((row) => row.kind === kind)
      .map((row) => ({ row, x: horizonToX(row.horizonDays) }))
      .sort((a, b) => a.x - b.x)
    const laneEnds: number[] = Array.from({ length: lanes }, () => Number.NEGATIVE_INFINITY)
    placed.forEach(({ row, x }, index) => {
      let lane = laneEnds.findIndex((end) => x - end >= minGap)
      if (lane === -1) lane = index % lanes
      laneEnds[lane] = x
      dots.push({ forecast: row, x, lane, side, size: dotSize(row.confidence) })
    })
  }
  return dots
}
