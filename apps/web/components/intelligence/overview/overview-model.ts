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
import type {
  IntelligenceAbilityMode,
  IntelligenceAbilityName,
  IntelligenceAbilitySetting,
  IntelligenceOverviewReadiness,
  IntelligencePageContextResponse,
  PromotionCandidate,
  RevenueOpportunities,
} from "@/lib/api"
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

/**
 * How much Gravitre can see across systems, from the Overview contract's
 * readiness (`GET /api/intelligence/overview`). The backend counts usable,
 * signed-in apps and never certifies coverage from a count, so:
 *   Limited:        no usable app, or only one.
 *   Cross-system:   two or more usable apps (a candidate, not verified coverage).
 *   Comprehensive:  only when the backend reports verified coverage.
 * There is no shared-account count in the backend, so the copy names the apps
 * and how many synced recently rather than a number of matched accounts.
 * Without the contract (older API) the same tiers come from the connector list.
 */
export function dataReadiness({
  connectors,
  readiness,
}: {
  connectors: Connector[] | null | undefined
  readiness?: IntelligenceOverviewReadiness | null
}): DataReadiness {
  const connected = connectedApps(connectors)
  const byVendor = new Map(connected.map((c) => [String(c.vendor ?? "").toLowerCase(), appName(c)]))
  const names = readiness
    ? readiness.vendors.map((vendor) => byVendor.get(vendor) ?? humanize(vendor))
    : connected.map(appName)
  const count = names.length
  const fresh = readiness ? readiness.fresh_count : null
  const apps = `${listNames(names.slice(0, 3))}${count > 3 ? ` and ${count - 3} more` : ""}`

  if (count === 0) {
    return {
      tier: "limited",
      label: "Limited",
      summary: "No apps are connected yet, so Gravitre only knows what your team tells it.",
    }
  }
  if (count === 1) {
    return {
      tier: "limited",
      label: "Limited",
      summary: `Only ${names[0]} is connected, so Gravitre can't find patterns across systems yet.`,
    }
  }
  const synced =
    fresh == null ? "" : fresh === count ? " All of them synced in the last three days." : ` ${fresh} of ${count} synced in the last three days.`
  if (readiness?.comprehensive && readiness.coverage_verified) {
    return { tier: "comprehensive", label: "Comprehensive", summary: `Gravitre reads ${apps}, with verified coverage across how you work.${synced}` }
  }
  return {
    tier: "cross-system",
    label: "Cross-system",
    summary: `Gravitre reads ${apps}, so it can look for patterns between them.${synced}`,
  }
}

// ---------------------------------------------------------------- at a glance

export type GlanceCard = {
  id: "revenue" | "hours" | "resolved" | "approval"
  label: string
  value: number | null
  certainty: Certainty
  hint: string
  link: { label: string; href: string }
  /** Opens the evidence panel (the records behind the number) instead of following the link. */
  evidence?: boolean
  /** ISO currency for money values (defaults to USD). */
  currency?: string
}

/** Compact money, e.g. $124.8K, in the currency the source recorded. */
export function formatMoneyCompact(value: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: value >= 10_000 ? "compact" : "standard",
    maximumFractionDigits: value >= 10_000 ? 1 : 0,
  }).format(value)
}

/** "Revenue opportunities": open CRM deal amounts, never estimates. */
export function revenueOpportunityCard(
  opportunities: RevenueOpportunities | null | undefined,
  routes: { connectors: string },
): GlanceCard {
  const base = { id: "revenue" as const, label: "Revenue opportunities" }
  if (!opportunities) {
    return { ...base, value: null, certainty: "none", hint: "Reading open deals from your CRM…", link: { label: "See the deals", href: routes.connectors } }
  }
  if (opportunities.status === "not_connected") {
    return {
      ...base,
      value: null,
      certainty: "none",
      hint: "Connect HubSpot to see open deal value. Gravitre counts only amounts recorded there.",
      link: { label: "Connect HubSpot", href: routes.connectors },
    }
  }
  if (opportunities.status !== "ready") {
    return {
      ...base,
      value: null,
      certainty: "none",
      hint: opportunities.error ?? "HubSpot couldn't be read just now.",
      link: { label: opportunities.status === "needs_reconnect" ? "Reconnect HubSpot" : "Open Connectors", href: routes.connectors },
    }
  }
  const n = opportunities.count
  const window = `the next ${opportunities.lookaheadDays} days`
  return {
    ...base,
    value: opportunities.total,
    certainty: opportunities.total == null ? "none" : "measured",
    hint:
      n === 0
        ? opportunities.unpricedCount > 0
          ? `${opportunities.unpricedCount} open ${opportunities.unpricedCount === 1 ? "deal closes" : "deals close"} in ${window}, but none has an amount in HubSpot.`
          : `No open deals in HubSpot close in ${window}.`
        : `Open deal value in HubSpot closing in ${window}.`,
    link: { label: n > 0 ? `Based on ${n} ${n === 1 ? "deal" : "deals"}` : "How this is counted", href: routes.connectors },
    evidence: true,
    currency: opportunities.currency,
  }
}

export function glanceCards({
  roi,
  metrics,
  opportunities,
  routes,
}: {
  roi: AgentRoiReport | null | undefined
  metrics: Metrics | null
  opportunities?: RevenueOpportunities | null
  routes: { impact: string; reports: string; approvals: string; plays: string; connectors: string }
}): GlanceCard[] {
  const totals = impactTotals(roi)
  const tasks = totals.tasks
  const resolved = num(metrics?.outcomes?.measuredOutcomes)
  const awaiting = num(metrics?.execution?.awaitingApproval)
  return [
    revenueOpportunityCard(opportunities, routes),
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
  /** Chip prefix; "Suggested" unless the source names a Play. */
  suggestionLabel?: string
  meta: string[]
  at: number | null
  actionLabel: string
  href: string
  /** Heuristic card id, when the item can be dismissed. */
  cardId?: string
  /** Detail panel: why Gravitre thinks this, in plain words, from the source record. */
  why?: string[]
  /** Detail panel: what it looked at. */
  sources?: string[]
  /** Detail panel: technical details (label, value), for admins and analysts. */
  tech?: Array<[string, string]>
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
      why: f.drivers,
      sources: f.evidence,
      tech: [
        ["Confidence", f.confidence == null ? "Not given by the source" : `${Math.round(f.confidence * 100)}% · an estimate, not a fact`],
        ["Source", f.origin === "workflow_alert" ? "Workflow failure check" : "Forecast"],
        ["When", f.whenLabel || "No timing given"],
        ...(f.confidenceNote ? ([["Note", f.confidenceNote]] as Array<[string, string]>) : []),
      ],
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
      why: card.reason ? [card.reason] : [],
      sources: [humanize(card.kind)].filter(Boolean),
      tech: [
        ["Detection", "Rule based, from your connected apps and their usage"],
        ["Confidence", typeof card.confidence === "number" ? `${Math.round(card.confidence * 100)}%` : "Not given"],
        ["Actions taken", "None until someone acts on it"],
      ],
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
      sources: ["Organization memory"],
      tech: [["Learned", learning.learnedAt ? new Date(str(learning.learnedAt)).toLocaleString("en-US") : "Date not recorded"]],
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
      sources: ["Outcome ledger"],
      tech: [
        ["Event", str(event.event)],
        ...(entity ? ([["Recorded for", entity]] as Array<[string, string]>) : []),
        ...(event.createdAt ? ([["At", new Date(str(event.createdAt)).toLocaleString("en-US")]] as Array<[string, string]>) : []),
      ],
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

/**
 * The seven abilities the intelligence router applies to every question
 * (`CAPABILITY_NAMES` in the backend), in the order and words of the Overview
 * design. Each ability's mode and on/off state come from the Overview contract.
 * Examples are generic on purpose: they describe the behavior, not a customer.
 */
export const ABILITY_MODES: Array<{ id: IntelligenceAbilityMode; label: string }> = [
  { id: "conservative", label: "Conservative" },
  { id: "balanced", label: "Balanced" },
  { id: "proactive", label: "Proactive" },
]

type AbilityCopy = {
  id: IntelligenceAbilityName
  label: string
  detail: string
  example: string
  /** 24px icon path from the design. */
  path: string
  /** Safe to turn off: answers get less rich, never wrong or unsafe. */
  canTurnOff: boolean
  /** Footnote under the controls. */
  why: string
  modes: Record<IntelligenceAbilityMode, string>
}

export const ABILITY_CATALOG: AbilityCopy[] = [
  {
    id: "contextual",
    label: "Understands context",
    detail: "Works out what a question is about, which account or deal it means, and what matters to the answer.",
    example: "When you ask how an account is doing, it works out which account you mean and looks at its renewal, tickets and contacts.",
    path: "M4 12h16M4 6h10M4 18h7",
    canTurnOff: false,
    why: "Always on. Gravitre needs it to understand what you are asking.",
    modes: {
      conservative: "Only uses the account or deal you name. Asks when a question is unclear.",
      balanced: "Infers the likely account or deal from recent work, and asks when unsure.",
      proactive: "Fills in context from your recent work and open items without asking.",
    },
  },
  {
    id: "sentiment",
    label: "Reads tone",
    detail: "Notices frustration or urgency in messages so replies and alerts fit the moment.",
    example: "A customer writing \u201cthird time asking\u201d gets flagged for a faster, more careful reply.",
    path: "M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
    canTurnOff: true,
    why: "Safe to turn off. Replies and alerts just stop adapting to tone.",
    modes: {
      conservative: "Only flags clear frustration, such as repeated complaints or escalation words.",
      balanced: "Flags frustration and urgency and suggests a faster or gentler reply.",
      proactive: "Also flags subtle signs, like shorter replies or slower responses, earlier.",
    },
  },
  {
    id: "temporal",
    label: "Tracks time",
    detail: "Keeps dates, deadlines and freshness in mind, so old information is not treated as current.",
    example: "It warns when a renewal is weeks away and when the notes it is using are months old.",
    path: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
    canTurnOff: false,
    why: "Always on. It keeps old information from being treated as current.",
    modes: {
      conservative: "Warns about anything older than 30 days and leans on the newest sources.",
      balanced: "Warns when information is older than 60 days or a deadline is within 2 weeks.",
      proactive: "Watches deadlines further out and suggests timing for follow-ups.",
    },
  },
  {
    id: "relational",
    label: "Connects relationships",
    detail: "Links people, companies, deals and tickets so it sees the whole picture.",
    example: "It connects a main contact leaving a customer with that customer\u2019s upcoming renewal.",
    path: "M6 6h.01M18 6h.01M12 18h.01M7 7l4 9M17 7l-4 9M7 6h10",
    canTurnOff: false,
    why: "Always on. Account answers depend on knowing who is connected to what.",
    modes: {
      conservative: "Uses only links confirmed in your apps, like a contact on a deal.",
      balanced: "Also uses links that appear often in emails and tickets.",
      proactive: "Suggests likely links it has not confirmed yet, clearly marked as suggestions.",
    },
  },
  {
    id: "causal",
    label: "Explains causes",
    detail: "Looks for what might be driving a change, and says plainly when it can only see a correlation.",
    example: "It says a spike in failed sign-ins is likely related to a settings change, without claiming proof.",
    path: "M5 12h4l3-8 3 16 3-8h1",
    canTurnOff: true,
    why: "Safe to turn off. Gravitre will describe what changed without suggesting why.",
    modes: {
      conservative: "Only explains a cause when the evidence is strong. Otherwise says it is unclear.",
      balanced: "Shares likely causes, labeled as correlation when it cannot confirm them.",
      proactive: "Offers more possible causes to investigate, each with how sure it is.",
    },
  },
  {
    id: "predictive",
    label: "Predicts",
    detail: "Estimates what is likely to happen next, like which customers may leave or what revenue to expect.",
    example: "It estimates which renewals are at risk, and says when an estimate comes from a simple average.",
    path: "M4 19h16M7 15l3-4 3 3 5-7",
    canTurnOff: true,
    why: "Safe to turn off. Gravitre will stop forecasting and only report what has happened.",
    modes: {
      conservative: "Only shows predictions from fully validated models.",
      balanced: "Shows predictions, using simpler estimates where a model is not ready, and says so.",
      proactive: "Predicts earlier with less data, with wider ranges and a clear warning.",
    },
  },
  {
    id: "adaptive",
    label: "Adapts to you",
    detail: "Learns from what your team approves, edits and ignores, so suggestions get more useful over time.",
    example: "After your team removes the same kind of line from a few drafts, Gravitre stops suggesting it.",
    path: "M4 4v6h6M20 20v-6h-6M5 13a7 7 0 0 0 12 4M19 11A7 7 0 0 0 7 7",
    canTurnOff: true,
    why: "Safe to turn off. Suggestions stay the same no matter how your team responds.",
    modes: {
      conservative: "Changes suggestions only after the same feedback repeats many times.",
      balanced: "Learns from approvals, edits and dismissals over a few weeks.",
      proactive: "Adjusts quickly after a handful of approvals or edits.",
    },
  },
]

export type Ability = AbilityCopy & {
  mode: IntelligenceAbilityMode | null
  /** False only when an admin turned a safe ability off. */
  enabled: boolean
}

export function sevenAbilities(
  capabilities: Partial<Record<IntelligenceAbilityName, IntelligenceAbilitySetting>> | null | undefined,
): Ability[] {
  return ABILITY_CATALOG.map((ability) => {
    const setting = capabilities?.[ability.id]
    return {
      ...ability,
      canTurnOff: setting?.can_turn_off ?? ability.canTurnOff,
      mode: setting?.mode ?? null,
      enabled: !(ability.canTurnOff && setting?.enabled === false),
    }
  })
}

// ---------------------------------------------------------------- readiness by business area

export type ReadinessDepth = "Good" | "Partial" | "Missing"

export const READINESS_AREAS: Array<{ name: string; vendors: string[]; missing: string }> = [
  { name: "Customers and sales", vendors: ["hubspot", "salesforce", "pipedrive", "zoho_crm", "close", "attio", "gong"], missing: "Connect HubSpot or Salesforce" },
  { name: "Support", vendors: ["zendesk", "intercom", "freshdesk", "helpscout", "front", "jira_service_management"], missing: "Connect Zendesk or Intercom" },
  { name: "Billing", vendors: ["stripe", "chargebee", "recurly", "paddle"], missing: "Connect Stripe" },
  { name: "Marketing", vendors: ["ga4", "google_analytics", "google_ads", "meta_ads", "linkedin_ads", "mailchimp", "klaviyo", "marketo"], missing: "Connect GA4 or Google Ads" },
  { name: "Accounting", vendors: ["quickbooks", "xero", "netsuite", "freshbooks", "sage"], missing: "Connect QuickBooks or Xero" },
]

export type ReadinessArea = { name: string; depth: ReadinessDepth; src: string; level: number; cta: string }

/**
 * Readiness per business area. Good = an app for the area synced in the last
 * three days; Partial = connected but not synced recently; Missing = nothing
 * connected. History depth isn't measured, so no area is ever called "Rich".
 */
export function readinessAreas({
  connectors,
  readiness,
}: {
  connectors: Connector[] | null | undefined
  readiness?: IntelligenceOverviewReadiness | null
}): ReadinessArea[] {
  const connected = connectedApps(connectors)
  const names = new Map(connected.map((c) => [String(c.vendor ?? "").toLowerCase(), appName(c)]))
  const vendors = readiness ? readiness.vendors.map((v) => v.toLowerCase()) : [...names.keys()]
  const fresh = new Set((readiness?.fresh_connectors ?? []).map((v) => v.toLowerCase()))
  const recent = Date.now() - 3 * 86_400_000
  const isFresh = (vendor: string) =>
    readiness
      ? fresh.has(vendor)
      : connected.some((c) => String(c.vendor).toLowerCase() === vendor && Date.parse(String(c.last_sync_at ?? "")) >= recent)
  return READINESS_AREAS.map((area) => {
    const here = vendors.filter((v) => area.vendors.includes(v))
    const label = listNames(here.map((v) => names.get(v) ?? humanize(v)))
    if (here.length === 0) return { name: area.name, depth: "Missing", src: "Not connected", level: 0, cta: area.missing }
    if (here.some(isFresh)) return { name: area.name, depth: "Good", src: `${label} · synced in the last 3 days`, level: 3, cta: "" }
    return { name: area.name, depth: "Partial", src: `${label} · not synced in the last 3 days`, level: 2, cta: "" }
  })
}

export function thinkingSummary({
  phrase,
  forecasts,
  hours,
  revenue,
  currency = "USD",
}: {
  phrase: string
  forecasts: Forecast[]
  hours: number | null
  /** Open deal value from the CRM (Revenue opportunities). */
  revenue: number | null
  currency?: string
}): string | null {
  const opportunities = forecasts.filter((f) => f.kind === "opportunity").length
  const risks = forecasts.filter((f) => f.kind === "risk").length
  const found: string[] = []
  if (revenue != null && revenue > 0) {
    found.push(`found ${formatMoneyCompact(revenue, currency)} in open revenue opportunities`)
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
