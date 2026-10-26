/**
 * Overview page model (Intelligence-Main design). Pure functions that turn the
 * intelligence engine's real responses into what the page shows:
 *
 * - page-context (`GET /api/intelligence/page-context`): knowledge, execution
 *   and outcome metrics, canonical predictions, auto-promoted learnings and
 *   the outcome ledger's recent events.
 * - agent ROI (`GET /api/enterprise/agent-roi`): hours saved and revenue
 *   influenced, each with its provenance.
 * - connectors (`GET /api/connectors`): which apps Gravitre reads.
 * - memory promotion candidates: patterns waiting for a person.
 * - heuristic recommendation cards (`GET /api/intelligence/recommendations/heuristics`).
 *
 * Nothing is invented: a number with no evidence is null and renders as a dash.
 */
import type { FailureAlertWithEvidence, Forecast } from "@/components/intelligence/forecasts/forecast-model"
import { buildForecasts } from "@/components/intelligence/forecasts/forecast-model"
import { impactTotals, type Certainty } from "@/components/intelligence/impact/impact-model"
import type { IntelligencePageContextResponse, PromotionCandidate } from "@/lib/api"
import type { AgentRoiReport, Connector } from "@/types/api"

export type OverviewPeriod = "today" | "week"

export const OVERVIEW_PERIODS: Record<OverviewPeriod, { label: string; windowHours: number; roiDays: number; phrase: string }> = {
  today: { label: "Today", windowHours: 24, roiDays: 1, phrase: "today" },
  week: { label: "This week", windowHours: 168, roiDays: 7, phrase: "this week" },
}

type Metrics = IntelligencePageContextResponse["metrics"]

function num(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  return null
}

function str(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

export function pageMetrics(ctx: IntelligencePageContextResponse | null | undefined): Metrics | null {
  return ctx?.metrics ?? ctx?.snapshot?.metrics ?? null
}

// ---------------------------------------------------------------- connectors

const CONNECTED = new Set(["active", "healthy", "connected", "syncing"])
const NEEDS_RECONNECT = new Set(["pending", "pending_auth", "needs_connection", "auth_expired", "error", "misconfigured"])

export function connectorStatus(c: Connector): string {
  return String(c.status ?? "").toLowerCase()
}

export function connectedApps(connectors: Connector[] | null | undefined): Connector[] {
  return (connectors ?? []).filter((c) => CONNECTED.has(connectorStatus(c)))
}

export function appsNeedingReconnect(connectors: Connector[] | null | undefined): Connector[] {
  return (connectors ?? []).filter((c) => NEEDS_RECONNECT.has(connectorStatus(c)))
}

export function appName(c: Connector): string {
  return (c.name || c.vendor || "App").trim()
}

export function listNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ""
  if (names.length === 2) return `${names[0]} and ${names[1]}`
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

// ---------------------------------------------------------------- data readiness

export type ReadinessTier = "limited" | "cross-system" | "comprehensive"

export const READINESS_TIERS: Array<{ id: ReadinessTier; label: string }> = [
  { id: "limited", label: "Limited" },
  { id: "cross-system", label: "Cross-system" },
  { id: "comprehensive", label: "Comprehensive" },
]

export type DataReadiness = { tier: ReadinessTier; label: string; summary: string }

/** Apps it takes before readiness counts as comprehensive, with links across them. */
export const COMPREHENSIVE_MIN_APPS = 4

/**
 * How much Gravitre can see across systems. Readiness grows with the number of
 * signed-in apps and whether the knowledge graph has linked records between
 * them; there is no shared-account count in the backend, so the copy names the
 * apps and the links rather than a number of matched accounts.
 *   Limited:        fewer than two apps, or nothing linked yet.
 *   Cross-system:   two or more apps with linked records.
 *   Comprehensive:  four or more apps with linked records, none waiting to sign in.
 */
export function dataReadiness({
  connectors,
  metrics,
}: {
  connectors: Connector[] | null | undefined
  metrics: Metrics | null
}): DataReadiness {
  const connected = connectedApps(connectors)
  const broken = appsNeedingReconnect(connectors)
  const links = num(metrics?.knowledge?.knownRelationships) ?? 0
  const names = connected.map(appName)

  if (connected.length === 0) {
    return {
      tier: "limited",
      label: "Limited",
      summary: "No apps are connected yet, so Gravitre only knows what your team tells it.",
    }
  }
  if (connected.length === 1) {
    return {
      tier: "limited",
      label: "Limited",
      summary: `Only ${names[0]} is connected, so Gravitre can't find patterns across systems yet.`,
    }
  }
  if (links === 0) {
    return {
      tier: "limited",
      label: "Limited",
      summary: `${listNames(names.slice(0, 3))}${names.length > 3 ? " and more" : ""} are connected, but Gravitre hasn't linked records between them yet.`,
    }
  }
  const linked = `Gravitre has linked ${links.toLocaleString("en-US")} ${links === 1 ? "record" : "records"} across ${listNames(names.slice(0, 3))}${names.length > 3 ? ` and ${names.length - 3} more` : ""}`
  if (connected.length >= COMPREHENSIVE_MIN_APPS && broken.length === 0) {
    return { tier: "comprehensive", label: "Comprehensive", summary: `${linked}, so it can find patterns across most of how you work.` }
  }
  return { tier: "cross-system", label: "Cross-system", summary: `${linked}, so it can find patterns between them.` }
}

// ---------------------------------------------------------------- at a glance

export type GlanceCard = {
  id: "revenue" | "hours" | "resolved" | "approval"
  label: string
  value: number | null
  certainty: Certainty
  hint: string
  link: { label: string; href: string }
}

export function glanceCards({
  roi,
  metrics,
  routes,
}: {
  roi: AgentRoiReport | null | undefined
  metrics: Metrics | null
  routes: { impact: string; reports: string; approvals: string; plays: string }
}): GlanceCard[] {
  const totals = impactTotals(roi)
  const tasks = totals.tasks
  const resolved = num(metrics?.outcomes?.measuredOutcomes)
  const awaiting = num(metrics?.execution?.awaitingApproval)
  return [
    {
      id: "revenue",
      label: "Revenue influenced",
      value: totals.revenue,
      certainty: totals.revenueCertainty,
      hint:
        totals.revenue == null
          ? "No verified deal value yet. Revenue counts only once your CRM confirms it."
          : "Won deal values your CRM confirmed after an agent acted.",
      link:
        totals.revenue == null
          ? { label: "Turn on revenue tracking", href: routes.plays }
          : { label: "See impact", href: routes.impact },
    },
    {
      id: "hours",
      label: "Hours potentially saved",
      value: totals.hours,
      certainty: totals.hoursCertainty,
      hint:
        tasks && tasks > 0
          ? `From ${tasks.toLocaleString("en-US")} finished ${tasks === 1 ? "task" : "tasks"}, estimated from task type.`
          : "Fills in once an agent finishes a task.",
      link: { label: tasks ? `Based on ${tasks.toLocaleString("en-US")} ${tasks === 1 ? "task" : "tasks"}` : "See impact", href: routes.impact },
    },
    {
      id: "resolved",
      label: "Issues resolved",
      value: resolved,
      certainty: resolved == null ? "none" : "measured",
      hint: "Each one confirmed by a result, not just acted on.",
      link: { label: resolved ? `Based on ${resolved} ${resolved === 1 ? "outcome" : "outcomes"}` : "See reports", href: routes.reports },
    },
    {
      id: "approval",
      label: "Awaiting approval",
      value: awaiting,
      certainty: awaiting == null ? "none" : "measured",
      hint: "Nothing runs until someone on your team approves.",
      link: { label: awaiting ? `Review ${awaiting} ${awaiting === 1 ? "item" : "items"}` : "Open approvals", href: routes.approvals },
    },
  ]
}

// ---------------------------------------------------------------- learning

export function pendingCandidates(candidates: PromotionCandidate[] | null | undefined): PromotionCandidate[] {
  return (candidates ?? []).filter((c) => str(c.status) === "pending_approval" && str(c.content))
}

/** Candidates first seen or reinforced inside the period window. */
export function candidatesInWindow(
  candidates: PromotionCandidate[] | null | undefined,
  windowHours: number,
  now: number = Date.now(),
): PromotionCandidate[] {
  const since = now - windowHours * 3_600_000
  return (candidates ?? []).filter((c) => {
    if (!str(c.content)) return false
    const at = Date.parse(str(c.updated_at) || str(c.created_at))
    return Number.isFinite(at) && at >= since
  })
}

export function candidateEvidence(c: PromotionCandidate): string {
  const seen = num(c.frequency)
  const teams = num(c.department_count)
  const parts: string[] = []
  if (seen) parts.push(`Seen ${seen} ${seen === 1 ? "time" : "times"}`)
  if (teams) parts.push(`in ${teams} ${teams === 1 ? "team" : "teams"}`)
  const head = parts.join(" ")
  const waiting = str(c.status) === "pending_approval" ? "waiting for review" : str(c.status).replace(/_/g, " ")
  return [head, waiting].filter(Boolean).join(" · ")
}

// ---------------------------------------------------------------- needs your attention

export type AttentionItem = {
  id: string
  text: string
  actionLabel: string
  href: string
  tone: "warning" | "danger" | "live"
}

export function attentionItems({
  connectors,
  metrics,
  pending,
  forecasts,
  routes,
}: {
  connectors: Connector[] | null | undefined
  metrics: Metrics | null
  pending: PromotionCandidate[]
  forecasts: Forecast[]
  routes: { connectors: string; approvals: string; memory: string; forecasts: string }
}): AttentionItem[] {
  const items: AttentionItem[] = []
  for (const c of appsNeedingReconnect(connectors)) {
    items.push({
      id: `connector:${c.id}`,
      text: `${appName(c)} needs to be signed in again before agents can read it`,
      actionLabel: "Reconnect",
      href: `${routes.connectors}/${encodeURIComponent(c.id)}`,
      tone: "danger",
    })
  }
  // awaitingApproval counts workflow approvals plus memory candidates waiting.
  const awaiting = num(metrics?.execution?.awaitingApproval) ?? 0
  const runs = Math.max(0, awaiting - pending.length)
  if (runs > 0) {
    items.push({
      id: "approvals",
      text: runs === 1 ? "A workflow run is waiting for your approval" : `${runs} workflow runs are waiting for your approval`,
      actionLabel: "Review",
      href: routes.approvals,
      tone: "warning",
    })
  }
  for (const f of forecasts.filter((row) => row.kind === "risk" && row.needsYouNow).slice(0, 2)) {
    items.push({ id: `forecast:${f.key}`, text: f.title, actionLabel: "Check", href: routes.forecasts, tone: "warning" })
  }
  if (pending.length > 0) {
    items.push({
      id: "memory",
      text: pending.length === 1 ? "A new pattern is waiting for your approval" : `${pending.length} new patterns are waiting for your approval`,
      actionLabel: "Review",
      href: routes.memory,
      tone: "live",
    })
  }
  return items
}

// ---------------------------------------------------------------- recent insights and activity

export type FeedKind = "insight" | "recommendation" | "action" | "outcome"

export const FEED_FILTERS: Array<{ id: FeedKind | "all"; label: string }> = [
  { id: "all", label: "All" },
  { id: "insight", label: "Insights" },
  { id: "recommendation", label: "Recommendations" },
  { id: "action", label: "Actions" },
  { id: "outcome", label: "Outcomes" },
]

export type FeedItem = {
  id: string
  kind: FeedKind
  title: string
  detail: string
  /** "Suggested next step" chip, when the source names one. */
  suggestion: string | null
  meta: string[]
  at: number | null
  actionLabel: string
  href: string
  /** Heuristic card id, when the item can be dismissed. */
  cardId?: string
}

type HeuristicCard = { id: string; kind: string; title: string; reason: string; href: string; confidence?: number }

/** Outcome-ledger events in plain words. Inflow events (created / generated) are not activity. */
const EVENT_COPY: Record<string, { kind: FeedKind; title: string }> = {
  workflow_executed: { kind: "action", title: "A workflow finished" },
  workflow_failed: { kind: "action", title: "A workflow run failed" },
  workflow_cancelled: { kind: "action", title: "A workflow run was cancelled" },
  connector_action_executed: { kind: "action", title: "Gravitre made a change in a connected app" },
  connector_action_failed: { kind: "action", title: "A change in a connected app failed" },
  approval_required: { kind: "action", title: "An action is waiting for approval" },
  crm_contacted: { kind: "action", title: "A contact was reached" },
  recommendation_approved: { kind: "outcome", title: "A recommendation was approved" },
  recommendation_rejected: { kind: "outcome", title: "A recommendation was turned down" },
  prediction_validated: { kind: "outcome", title: "A forecast came true" },
  prediction_missed: { kind: "outcome", title: "A forecast did not happen" },
  business_metric_improved: { kind: "outcome", title: "A business metric improved" },
  business_metric_declined: { kind: "outcome", title: "A business metric declined" },
  user_feedback_positive: { kind: "outcome", title: "Someone marked an answer as helpful" },
  user_feedback_negative: { kind: "outcome", title: "Someone marked an answer as not helpful" },
  approval_granted: { kind: "outcome", title: "An approval was granted" },
  approval_denied: { kind: "outcome", title: "An approval was denied" },
  crm_replied: { kind: "outcome", title: "A contact replied" },
  crm_booked: { kind: "outcome", title: "A meeting was booked" },
  crm_won: { kind: "outcome", title: "A deal was won" },
  crm_lost: { kind: "outcome", title: "A deal was lost" },
}

function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ""
}

function parseTime(value: unknown): number | null {
  const at = Date.parse(str(value))
  return Number.isFinite(at) ? at : null
}

export function buildFeed({
  ctx,
  forecasts,
  cards,
  routes,
}: {
  ctx: IntelligencePageContextResponse | null | undefined
  forecasts: Forecast[]
  cards: HeuristicCard[] | null | undefined
  routes: { forecasts: string; activity: string; reports: string; memory: string }
}): FeedItem[] {
  const items: FeedItem[] = []
  const predictions = new Map<string, Record<string, unknown>>(
    (ctx?.snapshot?.predictions ?? []).map((row) => [`prediction:${str(row.semanticKey) || str(row.id)}`, row] as const),
  )

  for (const f of forecasts) {
    const row = predictions.get(f.key)
    const actions = Array.isArray(row?.recommendedActions) ? (row?.recommendedActions as unknown[]).map(str).filter(Boolean) : []
    items.push({
      id: `forecast:${f.key}`,
      kind: actions.length > 0 ? "recommendation" : "insight",
      title: f.title,
      detail: f.summary,
      suggestion: actions[0] ?? null,
      meta: [str(row?.subject) === f.title ? "" : str(row?.subject), f.area ?? "", f.whenLabel].filter(Boolean),
      at: parseTime(row?.createdAt),
      actionLabel: actions.length > 0 ? "Review" : "Details",
      href: routes.forecasts,
    })
  }

  for (const card of cards ?? []) {
    if (!card?.id || !card.title) continue
    items.push({
      id: `card:${card.id}`,
      kind: "recommendation",
      title: card.title,
      detail: card.reason,
      suggestion: null,
      meta: [humanize(card.kind)].filter(Boolean),
      at: null,
      actionLabel: "Review",
      href: card.href || routes.forecasts,
      cardId: card.id,
    })
  }

  for (const learning of ctx?.snapshot?.learnings ?? []) {
    const statement = str(learning.businessStatement)
    if (!statement) continue
    items.push({
      id: `learning:${str(learning.id) || statement.slice(0, 24)}`,
      kind: "insight",
      title: "Gravitre learned a new pattern",
      detail: statement,
      suggestion: null,
      meta: ["Organization memory"],
      at: parseTime(learning.learnedAt),
      actionLabel: "Details",
      href: routes.memory,
    })
  }

  for (const event of ctx?.snapshot?.outcomes ?? []) {
    const copy = EVENT_COPY[str(event.event)]
    if (!copy) continue
    const entity = [humanize(str(event.entityType)), str(event.entityId)].filter(Boolean).join(" ")
    items.push({
      id: `event:${str(event.id) || `${str(event.event)}:${str(event.createdAt)}`}`,
      kind: copy.kind,
      title: copy.title,
      detail: entity ? `Recorded for ${entity}.` : "Recorded in the outcome ledger.",
      suggestion: null,
      meta: [humanize(str(event.department))].filter(Boolean),
      at: parseTime(event.createdAt),
      actionLabel: copy.kind === "action" ? "View" : "Details",
      href: copy.kind === "action" ? routes.activity : routes.reports,
    })
  }

  // Dated items newest first; undated recommendation cards keep their rank after the forecasts.
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => {
      if (a.item.at != null && b.item.at != null) return b.item.at - a.item.at
      if (a.item.at != null) return -1
      if (b.item.at != null) return 1
      return a.index - b.index
    })
    .map(({ item }) => item)
}

export function overviewForecasts(
  ctx: IntelligencePageContextResponse | null | undefined,
  failureAlerts?: FailureAlertWithEvidence[] | null,
): Forecast[] {
  return buildForecasts({ predictions: ctx?.snapshot?.predictions, failureAlerts })
}

// ---------------------------------------------------------------- how Gravitre thinks

/** The intelligence engine's seven abilities (POST /api/intelligence/{ask,explain,...}). */
export const SEVEN_ABILITIES: Array<{ id: string; label: string; detail: string }> = [
  { id: "ask", label: "Ask", detail: "Answers questions from your own knowledge, with sources." },
  { id: "explain", label: "Explain", detail: "Shows why a customer, deal or ticket looks the way it does." },
  { id: "recommend", label: "Recommend", detail: "Suggests the next step, with how sure it is." },
  { id: "forecast", label: "Forecast", detail: "Says what is likely to happen next, and when." },
  { id: "optimize", label: "Optimize", detail: "Finds slow or failing steps in your workflows." },
  { id: "plan", label: "Plan", detail: "Turns a goal into steps your agents can run." },
  { id: "execute", label: "Execute", detail: "Carries out an approved plan, never without the approvals you set." },
]

export function thinkingSummary({
  phrase,
  forecasts,
  hours,
  revenue,
}: {
  phrase: string
  forecasts: Forecast[]
  hours: number | null
  revenue: number | null
}): string | null {
  const opportunities = forecasts.filter((f) => f.kind === "opportunity").length
  const risks = forecasts.filter((f) => f.kind === "risk").length
  const found: string[] = []
  if (revenue != null && revenue > 0) {
    found.push(`influenced ${new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(revenue)} in revenue`)
  }
  if (risks + opportunities > 0) {
    const parts = [
      risks ? `${risks} ${risks === 1 ? "risk" : "risks"}` : "",
      opportunities ? `${opportunities} ${opportunities === 1 ? "opportunity" : "opportunities"}` : "",
    ].filter(Boolean)
    found.push(`spotted ${listNames(parts)}`)
  }
  if (hours != null && hours > 0) {
    found.push(`completed work that would have taken your team about ${Number(hours.toFixed(1))} hours`)
  }
  if (found.length === 0) return null
  const sentence = `${phrase.charAt(0).toUpperCase()}${phrase.slice(1)} Gravitre ${listNames(found)}.`
  return sentence
}
