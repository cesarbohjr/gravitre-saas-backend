import type { IntelligencePageContextResponse, PromotionCandidate } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import type { Connector } from "@/types/api"

/**
 * The Intelligence overview draws how signal moves through Gravitre:
 * Sources → Knowledge → Learning → Models → Forecasts.
 *
 * Live mode builds every node, edge and activity line from records the app
 * already fetches (page-context snapshot, connectors, memory candidates,
 * outcome attribution). A value the backend did not report stays null and
 * renders as "—" or the design's empty state, never as an invented number.
 */

export type FlowLayerId = "sources" | "knowledge" | "learning" | "models" | "forecasts"
export type FlowTone = "neutral" | "intelligence" | "approval" | "primary" | "brand" | "danger"

export type FlowLayer = {
  id: FlowLayerId
  name: string
  tone: FlowTone
  /** x position in the 1000-wide map viewBox. */
  x: number
  href: string
  page: string
  desc: string
  /** Short count line under the layer name, e.g. "4 sources". */
  count: string
}

export type FlowNode = {
  id: string
  layer: FlowLayerId
  label: string
  desc: string
  /** Mono line under the node label. */
  sub: string
  href: string
  /** Forecast nodes only: false draws the dashed "not scored yet" ring. */
  scored?: boolean
  /** Placeholder drawn when a layer has nothing yet. */
  placeholder?: boolean
  /** Signals that touched this node in the window; null when not measured. */
  signals?: number | null
}

export type FlowEdge = {
  key: string
  a: string
  b: string
  /** 0..6. Evidence edges grow with the records behind them. */
  weight: number
  /** True when a real record links the two nodes; false for the layer-to-layer flow. */
  evidence: boolean
}

export type FlowEventTone = "forward" | "feedback" | "danger" | "neutral" | "intelligence"

export type FlowEvent = {
  id: string
  text: string
  /** Node ids, upstream first. Two or more nodes can animate on the map. */
  path: string[]
  tone: FlowEventTone
  /** ISO time; null when the record has none. */
  at: string | null
}

export type FlowLearning = {
  id: string
  nodeId: string
  label: string
  desc: string
  reinforced: number | null
  /** 0..1, null when no confidence was recorded. */
  confidence: number | null
}

export type FlowQuiet = {
  /** Mono chip, e.g. "No signal since Mar 12". */
  since: string
  body: string
  /** Connectors that can be resynced from the overlay. */
  resyncIds: string[]
}

export type FlowStats = {
  signalsToday: number | null
  signalsSub: string
  connections: number | null
  connectionsSub: string
  outcomesFed: number | null
  outcomesTarget: number | null
  forecastValue: string
  forecastNote: string
  forecastScored: boolean
}

export type FlowModel = {
  example: boolean
  layers: FlowLayer[]
  nodes: FlowNode[]
  edges: FlowEdge[]
  events: FlowEvent[]
  learnings: FlowLearning[]
  stats: FlowStats
  coreState: { label: string; tone: FlowTone }
  /** Latest real signal time, for the core note. */
  lastSignalAt: string | null
  quiet: FlowQuiet | null
}

export const MAP_WIDTH = 1000
export const MAP_HEIGHT = 540
const MAP_TOP = 60
const MAP_SPAN = 420
const MAX_PER_LAYER = 5

export const LAYER_BASE: Array<Omit<FlowLayer, "count">> = [
  {
    id: "sources",
    name: "Sources",
    tone: "neutral",
    x: 100,
    href: APP_ROUTES.intelligenceData,
    page: "Data",
    desc: "Where signal comes in: your connected tools, plus every approval, edit and run your team does in Gravitre.",
  },
  {
    id: "knowledge",
    name: "Knowledge",
    tone: "intelligence",
    x: 300,
    href: APP_ROUTES.learning,
    page: "Knowledge",
    desc: "The things your business is made of, and how they relate to each other.",
  },
  {
    id: "learning",
    name: "Learning",
    tone: "approval",
    x: 500,
    href: APP_ROUTES.intelligenceMemory,
    page: "Memory",
    desc: "Patterns Gravitre noticed repeating across runs and confirmed by real outcomes.",
  },
  {
    id: "models",
    name: "Models",
    tone: "primary",
    x: 700,
    href: APP_ROUTES.models,
    page: "Models",
    desc: "Models that turn knowledge and learnings into predictions your agents use.",
  },
  {
    id: "forecasts",
    name: "Forecasts",
    tone: "brand",
    x: 900,
    href: APP_ROUTES.intelligencePredictive,
    page: "Forecasts",
    desc: "Predictions about what happens next, scored against what actually happened.",
  },
]

export const LAYER_ORDER: FlowLayerId[] = LAYER_BASE.map((l) => l.id)

export function layerById(layers: FlowLayer[], id: FlowLayerId): FlowLayer {
  return layers.find((l) => l.id === id) ?? { ...LAYER_BASE[0], count: "" }
}

/** Vertical position of a node within its column, matching the design's spacing. */
export function nodeY(index: number, total: number): number {
  return MAP_TOP + (index + 0.5) * (MAP_SPAN / Math.max(1, total))
}

export function edgeKey(a: string, b: string): string {
  return `${a}>${b}`
}

// ---------- small helpers ----------

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

function ratio(value: unknown): number | null {
  const n = typeof value === "string" ? Number(value) : num(value)
  if (n == null || !Number.isFinite(n)) return null
  return Math.max(0, Math.min(1, n > 1 ? n / 100 : n))
}

export function humanize(value: string): string {
  const text = value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1).toLowerCase() : value
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1).trimEnd()}…` : value
}

function plural(n: number, one: string, many = `${one}s`): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`
}

function timeMs(at: string | null | undefined): number {
  const ms = Date.parse(at ?? "")
  return Number.isFinite(ms) ? ms : 0
}

export function shortDate(at: string | null): string {
  const ms = timeMs(at)
  if (!ms) return ""
  return new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric" })
}

/** "now", "8s", "4m", "3h", "2d", or the date for anything older than a week. */
export function agoLabel(at: string | null, now: number): string {
  const ms = timeMs(at)
  if (!ms) return ""
  const sec = Math.max(0, Math.round((now - ms) / 1000))
  if (sec < 2) return "now"
  if (sec < 60) return `${sec}s`
  const min = Math.round(sec / 60)
  if (min < 60) return `${min}m`
  const hours = Math.round(min / 60)
  if (hours < 48) return `${hours}h`
  const days = Math.round(hours / 24)
  return days <= 7 ? `${days}d` : shortDate(at)
}

// ---------- outcome events ----------

const EVENT_TEXT: Record<string, string> = {
  recommendation_created: "Gravitre made a recommendation",
  recommendation_approved: "A teammate approved a recommendation",
  recommendation_rejected: "A teammate turned down a recommendation",
  prediction_generated: "A new forecast was made",
  prediction_validated: "Outcome: a forecast came true",
  prediction_missed: "Outcome: a forecast missed",
  workflow_executed: "A workflow ran",
  workflow_failed: "A workflow run failed",
  workflow_cancelled: "A workflow run was cancelled",
  connector_action_executed: "An agent updated a connected tool",
  connector_action_failed: "An agent could not update a connected tool",
  business_metric_improved: "Outcome: a business metric improved",
  business_metric_declined: "Outcome: a business metric declined",
  user_feedback_positive: "A teammate marked a reply as helpful",
  user_feedback_negative: "A teammate flagged a reply as unhelpful",
  approval_required: "An agent asked for approval",
  approval_granted: "A teammate approved an agent's action",
  approval_denied: "A teammate declined an agent's action",
  crm_contacted: "A contact was reached",
  crm_replied: "Outcome: a contact replied",
  crm_booked: "Outcome: a meeting was booked",
  crm_won: "Outcome: a deal was won",
  crm_lost: "Outcome: a deal was lost",
}

/** Measured results flow back into the core; everything else moves forward. */
const FEEDBACK_EVENTS = new Set([
  "prediction_validated",
  "prediction_missed",
  "business_metric_improved",
  "business_metric_declined",
  "user_feedback_positive",
  "user_feedback_negative",
  "crm_replied",
  "crm_booked",
  "crm_won",
  "crm_lost",
])

const FAILED_EVENTS = new Set(["workflow_failed", "connector_action_failed"])

export function outcomeEventText(event: string, department: string | null): string {
  const base = EVENT_TEXT[event] ?? humanize(event || "Outcome recorded")
  return department ? `${base} in ${humanize(department).toLowerCase()}` : base
}

// ---------- live model ----------

export type OutcomeAttribution = {
  minSampleSize?: number | null
  agentSummaries?: Array<{ sampleSize?: number | null; sufficientData?: boolean | null }>
} | null

export type LiveFlowInput = {
  pageContext?: IntelligencePageContextResponse | null
  connectors?: Connector[] | null
  candidates?: PromotionCandidate[] | null
  attribution?: OutcomeAttribution
  /** 0..1 average outcome confidence from the trust summary. */
  avgConfidence?: number | null
  loading?: boolean
}

const CORE_STATE: Record<string, { label: string; tone: FlowTone }> = {
  trace: { label: "Working", tone: "brand" },
  "flow-inward": { label: "Learning", tone: "brand" },
  resolved: { label: "Learning", tone: "brand" },
  "pending-approval": { label: "Waiting on you", tone: "approval" },
  "low-confidence": { label: "Low confidence", tone: "approval" },
  idle: { label: "Idle", tone: "approval" },
}

const MODEL_STATUS: Record<string, string> = {
  ready: "ready",
  recently_trained: "recently trained",
  trained: "trained",
  collecting: "collecting data",
  insufficient_data: "needs more data",
  not_started: "not started",
}

const OPEN_CANDIDATE = new Set(["candidate", "pending_approval", "pending"])
const PLATFORM_ID = "src:platform"

function placeholderNode(layer: FlowLayerId): FlowNode {
  const base = LAYER_BASE.find((l) => l.id === layer)!
  const copy: Record<FlowLayerId, string> = {
    sources: "No sources are connected yet.",
    knowledge: "Gravitre has not mapped any of your records yet.",
    learning: "No patterns have repeated often enough to count yet.",
    models: "No models are tracking your data yet.",
    forecasts: "No forecasts yet. They appear once a model has enough outcomes to predict from.",
  }
  return {
    id: `${layer}:none`,
    layer,
    label: "None yet",
    desc: copy[layer],
    sub: "",
    href: base.href,
    placeholder: true,
    scored: layer === "forecasts" ? false : undefined,
  }
}

function candidateConfidence(c: PromotionCandidate): number | null {
  const meta = (c.metadata ?? {}) as Record<string, unknown>
  return ratio(meta.confidence ?? meta.confidence_score ?? c.confidence)
}

export function buildLiveFlowModel(input: LiveFlowInput): FlowModel {
  const ctx = input.pageContext
  const snap: Partial<IntelligencePageContextResponse["snapshot"]> = ctx?.snapshot ?? {}
  const metrics = ctx?.metrics ?? snap.metrics
  const outcomes = ((snap.outcomes ?? []) as Array<Record<string, unknown>>).filter((o) => str(o.id))
  const learningsSnap = (snap.learnings ?? []) as Array<Record<string, unknown>>
  const predictions = (snap.predictions ?? []) as Array<Record<string, unknown>>
  const models = (snap.models ?? []) as Array<Record<string, unknown>>
  const connectors = input.connectors ?? []
  const nodes: FlowNode[] = []
  const evidence = new Map<string, number>()
  const link = (a: string, b: string, n = 1) => evidence.set(edgeKey(a, b), (evidence.get(edgeKey(a, b)) ?? 0) + n)

  // Sources: connected tools, plus what the team does inside Gravitre.
  const sortedConnectors = [...connectors]
    .sort((a, b) => Number(b.status === "active") - Number(a.status === "active") || timeMs(b.last_sync_at) - timeMs(a.last_sync_at))
    .slice(0, MAX_PER_LAYER - 1)
  for (const c of sortedConnectors) {
    const synced = c.last_sync_at ? `synced ${shortDate(c.last_sync_at)}` : humanize(c.status).toLowerCase()
    nodes.push({
      id: `src:${c.id}`,
      layer: "sources",
      label: truncate(c.name || humanize(c.vendor), 22),
      desc: `${humanize(c.vendor)} connection. ${c.status === "error" ? "The last sync failed." : c.last_sync_at ? `Last synced ${shortDate(c.last_sync_at)}.` : "Not synced yet."}`,
      sub: c.status === "error" ? "sync failed" : synced,
      href: `${APP_ROUTES.connectors}/${encodeURIComponent(c.id)}`,
    })
  }
  nodes.push({
    id: PLATFORM_ID,
    layer: "sources",
    label: "Team actions",
    desc: "Approvals, corrections and runs your team does inside Gravitre. Every one is a lesson.",
    sub: outcomes.length ? plural(outcomes.length, "signal") : "idle",
    href: APP_ROUTES.activity,
    signals: ctx ? outcomes.length : null,
  })

  // Knowledge: entity types Gravitre knows, plus any an outcome touched.
  const typeCounts = new Map<string, number>()
  for (const o of outcomes) {
    const t = str(o.entityType)
    if (t) typeCounts.set(t.toLowerCase(), (typeCounts.get(t.toLowerCase()) ?? 0) + 1)
  }
  const types: string[] = []
  for (const t of [...typeCounts.keys()].sort((a, b) => (typeCounts.get(b) ?? 0) - (typeCounts.get(a) ?? 0))) {
    if (!types.includes(t)) types.push(t)
  }
  for (const t of snap.knowledgeEntityTypes ?? []) {
    const key = String(t).toLowerCase()
    if (key && !types.includes(key)) types.push(key)
  }
  for (const t of types.slice(0, MAX_PER_LAYER)) {
    const n = typeCounts.get(t) ?? 0
    nodes.push({
      id: `kn:${t}`,
      layer: "knowledge",
      label: truncate(humanize(t), 22),
      desc: `${humanize(t)} records Gravitre knows about, joined across your sources.`,
      sub: n ? plural(n, "signal") : "",
      href: APP_ROUTES.learning,
      signals: n,
    })
    if (n) link(PLATFORM_ID, `kn:${t}`, n)
  }

  // Learning: patterns still being reinforced, then confirmed learnings.
  const openCandidates = (input.candidates ?? [])
    .filter((c) => str(c.content) && OPEN_CANDIDATE.has(String(c.status ?? "candidate")))
    .sort((a, b) => (num(b.frequency) ?? 0) - (num(a.frequency) ?? 0) || timeMs(b.updated_at) - timeMs(a.updated_at))
  const learnings: FlowLearning[] = []
  for (const c of openCandidates.slice(0, MAX_PER_LAYER)) {
    const content = String(c.content).trim()
    const freq = num(c.frequency)
    const nodeId = `lr:${c.id}`
    nodes.push({
      id: nodeId,
      layer: "learning",
      label: truncate(content, 24),
      desc: content,
      sub: freq ? `reinforced ${freq}×` : "new pattern",
      href: APP_ROUTES.intelligenceMemory,
    })
    learnings.push({
      id: c.id,
      nodeId,
      label: truncate(content, 60),
      desc: content,
      reinforced: freq,
      confidence: candidateConfidence(c),
    })
  }
  for (const l of learningsSnap) {
    if (nodes.filter((n) => n.layer === "learning").length >= MAX_PER_LAYER) break
    const id = str(l.id)
    const statement = str(l.businessStatement)
    if (!id || !statement) continue
    const nodeId = `lr:${id}`
    if (nodes.some((n) => n.id === nodeId)) continue
    nodes.push({
      id: nodeId,
      layer: "learning",
      label: truncate(statement, 24),
      desc: statement,
      sub: "in org memory",
      href: APP_ROUTES.intelligenceMemory,
    })
    for (const e of (l.affectedEntities as unknown[] | undefined) ?? []) {
      const t = str(e)?.toLowerCase()
      if (t && nodes.some((n) => n.id === `kn:${t}`)) link(`kn:${t}`, nodeId)
    }
    for (const m of (l.usedByModels as unknown[] | undefined) ?? []) {
      const slug = str(m)
      if (slug) link(nodeId, `md:${slug}`)
    }
  }

  // Models.
  for (const m of models.slice(0, MAX_PER_LAYER)) {
    const slug = str(m.id) ?? str(m.modelId)
    if (!slug) continue
    const status = str(m.status) ?? "unknown"
    nodes.push({
      id: `md:${slug}`,
      layer: "models",
      label: truncate(str(m.businessLabel) ?? humanize(slug), 22),
      desc: `${str(m.businessLabel) ?? humanize(slug)}. Status: ${MODEL_STATUS[status] ?? humanize(status).toLowerCase()}.`,
      sub: MODEL_STATUS[status] ?? humanize(status).toLowerCase(),
      href: APP_ROUTES.models,
    })
  }

  // Forecasts.
  const sortedPredictions = [...predictions]
    .filter((p) => str(p.id) && (str(p.subject) || str(p.businessStatement)))
    .sort((a, b) => (ratio(b.confidence) ?? -1) - (ratio(a.confidence) ?? -1))
  for (const p of sortedPredictions.slice(0, MAX_PER_LAYER)) {
    const conf = ratio(p.confidence)
    const nodeId = `fc:${String(p.id)}`
    nodes.push({
      id: nodeId,
      layer: "forecasts",
      label: truncate(str(p.subject) ?? str(p.businessStatement)!, 22),
      desc: str(p.businessStatement) ?? str(p.subject)!,
      sub: conf == null ? "not scored" : `${Math.round(conf * 100)}% confidence`,
      href: APP_ROUTES.intelligencePredictive,
      scored: conf != null,
    })
    const model = str(p.sourceModel)
    if (model) link(`md:${model}`, nodeId)
  }

  for (const id of LAYER_ORDER) {
    if (!nodes.some((n) => n.layer === id)) nodes.push(placeholderNode(id))
  }

  const edges = buildEdges(nodes, evidence)

  // Activity: outcome events, confirmed learnings, connector syncs. Newest first.
  const nodeIds = new Set(nodes.map((n) => n.id))
  const events: FlowEvent[] = []
  for (const o of outcomes) {
    const event = str(o.event) ?? "outcome"
    const t = str(o.entityType)?.toLowerCase()
    const kn = t && nodeIds.has(`kn:${t}`) ? `kn:${t}` : null
    const feedback = FEEDBACK_EVENTS.has(event)
    const path = kn ? (feedback ? [kn, PLATFORM_ID] : [PLATFORM_ID, kn]) : [PLATFORM_ID]
    events.push({
      id: `outcome:${String(o.id)}`,
      text: outcomeEventText(event, str(o.department)),
      path,
      tone: FAILED_EVENTS.has(event) ? "danger" : feedback ? "feedback" : "forward",
      at: str(o.createdAt),
    })
  }
  for (const l of learningsSnap) {
    const id = str(l.id)
    const statement = str(l.businessStatement)
    if (!id || !statement || !nodeIds.has(`lr:${id}`)) continue
    events.push({
      id: `learning:${id}`,
      text: `Gravitre learned: ${truncate(statement, 90)}`,
      path: [`lr:${id}`],
      tone: "feedback",
      at: str(l.learnedAt),
    })
  }
  for (const c of sortedConnectors) {
    if (c.status === "error") {
      events.push({
        id: `connector-error:${c.id}`,
        text: `${c.name || humanize(c.vendor)} stopped syncing. Reconnect it to keep signal flowing.`,
        path: [`src:${c.id}`],
        tone: "danger",
        at: c.updated_at ?? c.last_sync_at ?? null,
      })
    } else if (c.last_sync_at) {
      events.push({
        id: `connector-sync:${c.id}`,
        text: `Last sync from ${c.name || humanize(c.vendor)}`,
        path: [`src:${c.id}`],
        tone: "neutral",
        at: c.last_sync_at,
      })
    }
  }
  events.sort((a, b) => timeMs(b.at) - timeMs(a.at))

  // Stats.
  const signalsToday = num(metrics?.outcomes?.outcomeEventsInWindow) ?? (ctx ? outcomes.length : null)
  const windowHours = num(snap.timeWindowHours) ?? 24
  const relationships = num(metrics?.learning?.relationshipsLearned) ?? num(metrics?.knowledge?.knownRelationships)
  const summaries = input.attribution?.agentSummaries ?? []
  const target = num(input.attribution?.minSampleSize)
  const best = summaries.length ? Math.max(0, ...summaries.map((s) => num(s.sampleSize) ?? 0)) : input.attribution ? 0 : null
  const scored = summaries.some((s) => s.sufficientData)
  const avg = ratio(input.avgConfidence)
  let forecastValue = "None yet"
  let forecastNote = "Scoring starts once outcomes are measured"
  if (scored && avg != null) {
    forecastValue = `${Math.round(avg * 100)}%`
    forecastNote = `Scored against ${plural(best ?? 0, "real outcome")}`
  } else if (target != null && best != null && best > 0) {
    forecastValue = "Calibrating"
    forecastNote = `${plural(Math.max(0, target - best), "outcome")} until scoring starts`
  } else if (target != null) {
    forecastNote = `${plural(target, "more outcome")} needed`
  }

  const stats: FlowStats = {
    signalsToday,
    signalsSub: `Every sync, run and click that reached the core in the last ${windowHours === 24 ? "24 hours" : `${windowHours} hours`}`,
    connections: relationships,
    connectionsSub: "Links between your records that Gravitre has confirmed",
    outcomesFed: best,
    outcomesTarget: target,
    forecastValue,
    forecastNote,
    forecastScored: scored && avg != null,
  }

  // Layer counts.
  const knownEntities = num(metrics?.knowledge?.knownEntities)
  const learningTotal = openCandidates.length + learningsSnap.length
  const scoredForecasts = sortedPredictions.filter((p) => ratio(p.confidence) != null).length
  const unscored = sortedPredictions.length - scoredForecasts
  const counts: Record<FlowLayerId, string> = {
    sources: plural(connectors.length, "source"),
    knowledge: knownEntities != null ? plural(knownEntities, "entity", "entities") : plural(types.length, "entity type"),
    learning: plural(learningTotal, "learning"),
    models: plural(num(metrics?.learning?.modelsTracked) ?? models.length, "model"),
    forecasts:
      sortedPredictions.length === 0
        ? "0 forecasts"
        : unscored === 0
          ? `${scoredForecasts} scored`
          : scoredForecasts === 0
            ? `${unscored} unscored`
            : `${scoredForecasts} scored · ${unscored} unscored`,
  }
  const layers = LAYER_BASE.map((l) => ({ ...l, count: counts[l.id] }))

  // Quiet: nothing reached the core in the window.
  const windowStart = timeMs(snap.generatedAt) - windowHours * 3_600_000
  const recent = events.some(
    (e) => (e.id.startsWith("outcome:") || e.id.startsWith("learning:")) && timeMs(e.at) >= windowStart,
  )
  const lastSignalAt = events.find((e) => e.at)?.at ?? null
  let quiet: FlowQuiet | null = null
  if (ctx && !input.loading && !recent && !(signalsToday ?? 0)) {
    const syncTimes = connectors.map((c) => timeMs(c.last_sync_at)).filter(Boolean)
    const lastSync = syncTimes.length ? Math.max(...syncTimes) : 0
    const days = lastSync ? Math.max(1, Math.round((Date.now() - lastSync) / 86_400_000)) : 0
    const body =
      connectors.length === 0
        ? "No sources are connected yet, so nothing is flowing. Connect one to bring this map to life, or watch it with example data."
        : lastSync
          ? `${connectors.length === 1 ? "Your only source" : `All ${connectors.length} sources`} last synced ${plural(days, "day")} ago, so nothing new is flowing. Resync to bring this map to life, or watch it with example data.`
          : `${connectors.length === 1 ? "Your source has" : `Your ${connectors.length} sources have`} not synced yet, so nothing is flowing. Resync to bring this map to life, or watch it with example data.`
    quiet = {
      since: lastSignalAt ? `No signal since ${shortDate(lastSignalAt)}` : "No signal yet",
      body,
      resyncIds: connectors.filter((c) => c.status !== "inactive").map((c) => c.id),
    }
  }

  const coreState = quiet
    ? { label: "Idle", tone: "approval" as FlowTone }
    : (CORE_STATE[str(snap.coreState) ?? ""] ?? { label: input.loading ? "Loading" : "Idle", tone: "neutral" as FlowTone })

  return {
    example: false,
    layers,
    nodes,
    edges,
    events: events.slice(0, 12),
    learnings: learnings.slice(0, 3),
    stats,
    coreState,
    lastSignalAt,
    quiet,
  }
}

/**
 * Evidence edges come from real records. A node with no recorded link to the
 * neighbouring layer still joins it with a thin flow line, because every
 * layer feeds the next one in the pipeline; those lines never thicken.
 */
export function buildEdges(nodes: FlowNode[], evidence: Map<string, number>): FlowEdge[] {
  const byLayer = new Map<FlowLayerId, FlowNode[]>()
  for (const n of nodes) byLayer.set(n.layer, [...(byLayer.get(n.layer) ?? []), n])
  const ids = new Set(nodes.map((n) => n.id))
  const edges = new Map<string, FlowEdge>()
  for (const [key, count] of evidence) {
    const [a, b] = key.split(">")
    if (!ids.has(a) || !ids.has(b)) continue
    edges.set(key, { key, a, b, weight: Math.min(6, 1 + Math.log2(count + 1)), evidence: true })
  }
  for (let i = 0; i < LAYER_ORDER.length - 1; i++) {
    const left = byLayer.get(LAYER_ORDER[i]) ?? []
    const right = byLayer.get(LAYER_ORDER[i + 1]) ?? []
    const hasOut = (id: string) => [...edges.values()].some((e) => e.a === id && right.some((r) => r.id === e.b))
    const hasIn = (id: string) => [...edges.values()].some((e) => e.b === id && left.some((l) => l.id === e.a))
    const lonelyLeft = left.filter((l) => !hasOut(l.id))
    const lonelyRight = right.filter((r) => !hasIn(r.id))
    for (const l of left) {
      for (const r of right) {
        const key = edgeKey(l.id, r.id)
        if (edges.has(key)) continue
        if (lonelyLeft.includes(l) || lonelyRight.includes(r)) {
          edges.set(key, { key, a: l.id, b: r.id, weight: 0.4, evidence: false })
        }
      }
    }
  }
  return [...edges.values()]
}
