/**
 * Agents roster (Team / List / Work map) view model.
 *
 * Every number comes from GET /api/agents (identity, apps, model) joined with
 * GET /api/metrics/agent-roster (real agent_jobs aggregates, approval gates and
 * goal links). Nothing here invents values: a missing stat stays null and the
 * UI renders a calm "No runs yet" / "Not reported" instead.
 */
import { mapApiDepartmentToFleet } from "@/lib/agent-identity-bridge"
import { resolveProvider } from "@/lib/provider-registry"
import type { AgentDepartmentId } from "@/components/agents/fleet-v4/types"

export type RosterView = "team" | "list" | "graph"

export function isRosterView(value: unknown): value is RosterView {
  return value === "team" || value === "list" || value === "graph"
}

// ---- GET /api/metrics/agent-roster ------------------------------------------------

export interface RosterBlocked {
  kind: "failed" | "paused"
  reason: string
  jobId: string | null
  at: string
}

export interface RosterAgentStats {
  tasksToday: number
  failedToday: number
  runningNow: number
  successRateToday: number | null
  successRate7d: number | null
  lastActiveAt: string | null
  daily: number[]
  blocked: RosterBlocked | null
}

export interface RosterGoal {
  id: string
  objective: string
  status: string
  department?: string | null
  priority?: string | null
  connectedSystems: string[]
  agentIds: string[]
}

export interface RosterStatsPayload {
  generatedAt: string
  days: string[]
  agents: Record<string, RosterAgentStats>
  /** Agent id -> writes wait for approval. Missing ids fail closed (true). */
  approvalGate: Record<string, boolean>
  goals: RosterGoal[]
}

export function rosterStatsKey(): string {
  const tz = typeof window === "undefined" ? 0 : -new Date().getTimezoneOffset()
  return `/api/metrics/agent-roster?tz=${tz}`
}

// ---- Departments --------------------------------------------------------------------

export interface DepartmentMeta {
  id: AgentDepartmentId
  name: string
  blurb: string
  /** dept-* illustration in /public/illustrations, when the library has one. */
  illustration: string | null
  alt: string
  emptyHint: string
}

export const ROSTER_DEPARTMENTS: DepartmentMeta[] = [
  {
    id: "sales",
    name: "Sales",
    blurb: "Finds, enriches and moves accounts from first touch to closed deal.",
    illustration: "dept-sales",
    alt: "Two people shaking hands next to a growth chart",
    emptyHint: "No agents yet. Add one to find leads, enrich accounts or watch the pipeline.",
  },
  {
    id: "marketing",
    name: "Marketing",
    blurb: "Runs campaigns, watches search and AI visibility, and keeps content sharp.",
    illustration: "dept-marketing",
    alt: "Two people planning a campaign on a sticky note board",
    emptyHint: "No agents yet. Add one for campaigns, SEO or content.",
  },
  {
    id: "customer_success",
    name: "Customer Success",
    blurb: "Keeps customers healthy and every ticket in the right hands.",
    illustration: "dept-support",
    alt: "A support agent with a headset answering messages",
    emptyHint: "No agents yet. Add one to triage tickets or flag churn risk.",
  },
  {
    id: "operations",
    name: "Operations",
    blurb: "Keeps the day-to-day running, from vendor checks to internal reports.",
    illustration: "dept-operations",
    alt: "A person at a monitor with gears turning above",
    emptyHint: "No agents yet. Add one for reporting, vendor checks or handoffs.",
  },
  {
    id: "finance",
    name: "Finance",
    blurb: "Watches cash, invoices and spend so the numbers stay honest.",
    illustration: "dept-finance",
    alt: "A person at a desk with stacks of coins and a chart",
    emptyHint: "No agents yet. Add one for cash forecasts, invoices or spend reviews.",
  },
  {
    id: "engineering",
    name: "Engineering",
    blurb: "Reviews code, checks APIs and writes the release notes.",
    illustration: "dept-engineering",
    alt: "Two engineers pairing at a long desk with monitors",
    emptyHint: "No agents yet. Add one for code reviews, API checks or release notes.",
  },
  {
    id: "security",
    name: "Security",
    blurb: "Watches access, vulnerabilities and compliance evidence.",
    illustration: "dept-security",
    alt: "A person at a desk with a locked screen beside a shield",
    emptyHint: "No agents yet. Add one to watch access and vulnerabilities.",
  },
  {
    id: "general",
    name: "General",
    blurb: "Helpers that work across the whole workspace.",
    illustration: "dept-general",
    alt: "Two helpers by a toolbox and a board of sticky notes",
    emptyHint: "No agents yet. Add a general helper for everyday requests.",
  },
]

export const DEPARTMENT_BY_ID = new Map(ROSTER_DEPARTMENTS.map((d) => [d.id, d]))

// ---- Agents ----------------------------------------------------------------------------

export type RosterState = "working" | "blocked" | "active_today" | "ready" | "not_set_up"

export interface RosterAgent {
  id: string
  name: string
  role: string
  description: string
  department: AgentDepartmentId
  departmentLabel: string
  model: string
  apps: string[]
  capabilities: string[]
  status: string
  state: RosterState
  gated: boolean
  output: string | null
  stats: RosterAgentStats | null
  tasksToday: number
  successToday: number | null
  success7d: number | null
  lastActiveAt: string | null
}

type RawAgent = Record<string, unknown>

const PLACEHOLDER_DESCRIPTIONS = new Set(["", "ai teammate"])

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.map((v) => String(v ?? "").trim()).filter(Boolean) : []
}

/** Provider display name for a connector / system id ("hubspot" -> "HubSpot"). */
export function appDisplayName(raw: string): string {
  const entry = resolveProvider(raw)
  if (entry) return entry.name
  const spaced = raw.replace(/[_-]+/g, " ").trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function agentApps(raw: RawAgent): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const value of [
    ...strings(raw.connectedSystems),
    ...strings(raw.connected_systems),
    ...strings(raw.permissions),
    ...strings(raw.systems),
  ]) {
    const name = appDisplayName(value)
    const key = name.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    out.push(name)
  }
  return out
}

export function modelLabel(raw: RawAgent): string {
  const config = (raw.config ?? {}) as Record<string, unknown>
  const value = String(raw.model ?? config.model ?? "").trim()
  if (!value || value === "auto") return "default"
  return value.replace(/^openai\//, "").replace(/^anthropic\//, "")
}

// Ordered most specific first; the first match wins. Matches the agent's own
// name, role and capabilities, so the output is what this agent is set up to do.
const OUTPUT_RULES: Array<[RegExp, string]> = [
  [/enrich/, "Enriched contacts"],
  [/scout|prospect|lead gen|find.*lead|lead.*(find|search)|icp/, "Qualified leads"],
  [/forecast|pipeline|revenue|revops/, "Forecast and pipeline"],
  [/deal|qualif|sales agent|close/, "Deals moved"],
  [/macro|executive|brief/, "Executive briefs"],
  [/seo|visibility|search rank|ai assistant/, "Visibility reports"],
  [/campaign|sequence|email market|marketing agent|newsletter/, "Campaigns sent"],
  [/content|blog|copy/, "Content drafts"],
  [/ticket|triage|support|helpdesk/, "Tickets routed"],
  [/churn|health|renewal|customer success/, "Churn alerts"],
  [/vulnerab|risk|threat|security|compliance/, "Risk reports"],
  [/cash|invoice|billing|payable|receivable|spend|finance/, "Cash forecast"],
  [/code|review|release|api check|engineer/, "Code reviews"],
  [/report|analy/, "Reports"],
]

function humanize(value: string): string {
  const spaced = value.replace(/[_.:-]+/g, " ").replace(/\s+/g, " ").trim()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

export function deriveOutput(name: string, role: string, description: string, capabilities: string[]): string | null {
  const haystack = [name, role, description, ...capabilities].join(" ").toLowerCase()
  for (const [pattern, label] of OUTPUT_RULES) {
    if (pattern.test(haystack)) return label
  }
  if (capabilities[0]) return humanize(capabilities[0])
  return null
}

export function toRosterAgent(raw: RawAgent, stats: RosterStatsPayload | undefined): RosterAgent {
  const id = String(raw.id ?? "")
  const name = String(raw.name ?? "Agent")
  const roleRaw = String(raw.role ?? "").trim()
  const role = roleRaw && roleRaw !== name ? roleRaw : ""
  const descRaw = String(raw.description ?? "").trim()
  const description = PLACEHOLDER_DESCRIPTIONS.has(descRaw.toLowerCase()) ? "" : descRaw
  const dept = mapApiDepartmentToFleet(String(raw.department ?? ""))
  const apps = agentApps(raw)
  const capabilities = strings(raw.capabilities)
  const s = stats?.agents?.[id] ?? null
  const status = String(raw.status ?? "active")
  const notSetUp = !description && capabilities.length === 0 && apps.length === 0
  const blocked = Boolean(s?.blocked) || status === "error"
  const working = (s?.runningNow ?? 0) > 0 || status === "processing"
  const state: RosterState = blocked
    ? "blocked"
    : working
      ? "working"
      : (s?.tasksToday ?? 0) > 0
        ? "active_today"
        : notSetUp
          ? "not_set_up"
          : "ready"
  const gate = stats?.approvalGate?.[id]
  return {
    id,
    name,
    role,
    description,
    department: dept.id,
    departmentLabel: DEPARTMENT_BY_ID.get(dept.id)?.name ?? dept.label,
    model: modelLabel(raw),
    apps,
    capabilities,
    status,
    state,
    // Writes need an app to land in; with an app, the policy decides (fails closed).
    gated: apps.length > 0 && gate !== false,
    output: notSetUp ? null : deriveOutput(name, role, description, capabilities),
    stats: s,
    tasksToday: s?.tasksToday ?? 0,
    successToday: s?.successRateToday ?? null,
    success7d: s?.successRate7d ?? null,
    lastActiveAt: s?.lastActiveAt ?? null,
  }
}

export function normalizeAgentsPayload(payload: unknown): RawAgent[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.agents)
    ? model.agents
    : Array.isArray(model.operators)
      ? model.operators
      : Array.isArray(model.data)
        ? model.data
        : []
  return (raw as unknown[]).filter(
    (item): item is RawAgent => Boolean(item) && typeof item === "object" && Boolean((item as RawAgent).id),
  )
}

export function initials(name: string): string {
  const words = name.replace(/[[\]()]/g, " ").split(/\s+/).filter(Boolean)
  if (words.length === 0) return "AG"
  return ((words[0][0] ?? "") + (words[1]?.[0] ?? words[0][1] ?? "")).toUpperCase()
}

export function formatRate(rate: number | null): string | null {
  if (rate == null || !Number.isFinite(rate)) return null
  return `${Math.round(rate)}%`
}

export function formatLastActive(iso: string | null, now = new Date()): string {
  if (!iso) return "No runs yet"
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return "Not reported"
  const minutes = Math.round((now.getTime() - at.getTime()) / 60000)
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes} min ago`
  const sameDay = at.toDateString() === now.toDateString()
  if (sameDay) return "Today"
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (at.toDateString() === yesterday.toDateString()) return "Yesterday"
  const days = Math.round(minutes / 1440)
  if (days < 14) return `${days} days ago`
  return at.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

// ---- Team / List summaries ----------------------------------------------------------

export interface DepartmentGroup {
  meta: DepartmentMeta
  agents: RosterAgent[]
}

/** Departments with agents, busiest (most agents) first; ties keep fleet order. */
export function groupByDepartment(agents: RosterAgent[]): DepartmentGroup[] {
  return ROSTER_DEPARTMENTS.map((meta) => ({
    meta,
    agents: agents.filter((a) => a.department === meta.id).sort((x, y) => x.name.localeCompare(y.name)),
  }))
    .filter((g) => g.agents.length > 0)
    .sort((a, b) => b.agents.length - a.agents.length)
}

export function emptyDepartments(agents: RosterAgent[]): DepartmentMeta[] {
  const covered = new Set(agents.map((a) => a.department))
  return ROSTER_DEPARTMENTS.filter((d) => !covered.has(d.id))
}

/** Busiest agent today by completed tasks; null when nobody finished anything. */
export function standoutAgent(agents: RosterAgent[]): RosterAgent | null {
  let best: RosterAgent | null = null
  for (const a of agents) {
    if (a.tasksToday <= 0) continue
    if (!best || a.tasksToday > best.tasksToday) best = a
  }
  return best
}

/** Tasks an agent finished over the last `days` reported days (today included). */
export function recentTasks(agent: RosterAgent, days = 7): number {
  return (agent.stats?.daily ?? []).slice(-days).reduce((sum, n) => sum + n, 0)
}

/** Busiest agent over the last week; null when nobody finished anything in that window. */
export function weekStandoutAgent(agents: RosterAgent[], days = 7): { agent: RosterAgent; tasks: number } | null {
  let best: { agent: RosterAgent; tasks: number } | null = null
  for (const a of agents) {
    const tasks = recentTasks(a, days)
    if (tasks <= 0) continue
    if (!best || tasks > best.tasks) best = { agent: a, tasks }
  }
  return best
}

export function needsYou(agents: RosterAgent[]): RosterAgent[] {
  return agents.filter((a) => a.state === "blocked")
}

export function blockedReason(agent: RosterAgent): string | null {
  if (agent.stats?.blocked) return agent.stats.blocked.reason
  if (agent.status === "error") return "Reported an error and needs a look"
  return null
}

export function stateCounts(agents: RosterAgent[]) {
  const counts = { working: 0, ready: 0, blocked: 0, not_set_up: 0, active_today: 0 }
  for (const a of agents) counts[a.state] += 1
  return counts
}

// ---- Work map -------------------------------------------------------------------------

export interface MapApp {
  name: string
  agentIds: string[]
}

export interface MapOutput {
  name: string
  agentIds: string[]
  gated: boolean
  goalIds: string[]
}

export interface WorkMapModel {
  apps: MapApp[]
  noAppAgentIds: string[]
  agents: RosterAgent[]
  outputs: MapOutput[]
  goals: RosterGoal[]
  /** Goal id -> agent ids that feed it. */
  goalAgents: Map<string, string[]>
  unmeasuredOutputs: MapOutput[]
}

function overlaps(a: string[], b: string[]): boolean {
  const set = new Set(a.map((x) => x.toLowerCase()))
  return b.some((x) => set.has(x.toLowerCase()))
}

/**
 * Agents feeding a goal: the goal plan's required agents when it names them,
 * otherwise agents in the goal's department that use one of its apps (or any
 * agent in that department when the goal names no apps).
 */
export function goalFeeders(goal: RosterGoal, agents: RosterAgent[]): string[] {
  const known = new Set(agents.map((a) => a.id))
  const planned = goal.agentIds.filter((id) => known.has(id))
  if (planned.length > 0) return planned
  if (!goal.department) return []
  const dept = mapApiDepartmentToFleet(goal.department).id
  const systems = goal.connectedSystems.map(appDisplayName)
  return agents
    .filter((a) => a.department === dept && a.output)
    .filter((a) => systems.length === 0 || overlaps(a.apps, systems))
    .map((a) => a.id)
}

export function buildWorkMap(agents: RosterAgent[], goals: RosterGoal[]): WorkMapModel {
  const order = new Map(ROSTER_DEPARTMENTS.map((d, i) => [d.id, i]))
  const sorted = [...agents].sort((x, y) => {
    const dx = order.get(x.department) ?? 99
    const dy = order.get(y.department) ?? 99
    if (dx !== dy) return dx - dy
    if ((x.output ? 0 : 1) !== (y.output ? 0 : 1)) return x.output ? -1 : 1
    return x.name.localeCompare(y.name)
  })

  const appMap = new Map<string, string[]>()
  for (const a of sorted) for (const app of a.apps) appMap.set(app, [...(appMap.get(app) ?? []), a.id])
  const apps = [...appMap.entries()].map(([name, agentIds]) => ({ name, agentIds }))

  const goalAgents = new Map<string, string[]>()
  for (const g of goals) goalAgents.set(g.id, goalFeeders(g, sorted))

  const outMap = new Map<string, MapOutput>()
  for (const a of sorted) {
    if (!a.output) continue
    const o = outMap.get(a.output) ?? { name: a.output, agentIds: [], gated: false, goalIds: [] }
    o.agentIds.push(a.id)
    o.gated = o.gated || a.gated
    for (const [gid, ids] of goalAgents) if (ids.includes(a.id) && !o.goalIds.includes(gid)) o.goalIds.push(gid)
    outMap.set(a.output, o)
  }
  const outputs = [...outMap.values()]
  return {
    apps,
    noAppAgentIds: sorted.filter((a) => a.apps.length === 0).map((a) => a.id),
    agents: sorted,
    outputs,
    goals,
    goalAgents,
    unmeasuredOutputs: outputs.filter((o) => o.goalIds.length === 0),
  }
}

export type TraceKey = string // "all" | "goal:<id>" | "goal:none" | "agent:<id>" | "app:<name>" | "out:<name>"

export function litAgents(model: WorkMapModel, key: TraceKey): Set<string> {
  const [kind, ...rest] = key.split(":")
  const value = rest.join(":")
  const ids = new Set<string>()
  if (kind === "all" || !kind) {
    for (const a of model.agents) ids.add(a.id)
  } else if (kind === "goal" && value === "none") {
    for (const o of model.unmeasuredOutputs) for (const id of o.agentIds) ids.add(id)
  } else if (kind === "goal") {
    for (const id of model.goalAgents.get(value) ?? []) ids.add(id)
  } else if (kind === "agent") {
    ids.add(value)
  } else if (kind === "app") {
    for (const id of model.apps.find((p) => p.name === value)?.agentIds ?? []) ids.add(id)
  } else if (kind === "out") {
    for (const id of model.outputs.find((o) => o.name === value)?.agentIds ?? []) ids.add(id)
  }
  return ids
}

function list(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ""
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

const NUMBER_WORDS = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
function countWord(n: number): string {
  return NUMBER_WORDS[n] ?? String(n)
}

/** The plain-language sentence above the map, written from live data. */
export function traceStory(model: WorkMapModel, key: TraceKey): string {
  const [kind, ...rest] = key.split(":")
  const value = rest.join(":")
  const byId = new Map(model.agents.map((a) => [a.id, a]))
  if (kind === "all" || !kind) {
    return "Read it left to right. Green lines are working right now, grey are ready and waiting, amber is blocked. Every lock on the approval lane is an output that writes to one of your apps and waits for your OK first."
  }
  if (kind === "goal" && value === "none") {
    const n = model.unmeasuredOutputs.length
    if (n === 0) return "Every output on the map counts toward a goal."
    return `${countWord(n)} output${n === 1 ? " is" : "s are"} not tied to any goal: ${list(model.unmeasuredOutputs.map((o) => o.name.toLowerCase()))}. Link them to goals to measure what these agents deliver.`
  }
  if (kind === "goal") {
    const goal = model.goals.find((g) => g.id === value)
    if (!goal) return "This goal is no longer on the map."
    const feeders = (model.goalAgents.get(goal.id) ?? []).map((id) => byId.get(id)).filter(Boolean) as RosterAgent[]
    if (feeders.length === 0) {
      return `No agent feeds ${goal.objective} yet. Give it a plan or move an agent into its department to see the path.`
    }
    const parts = feeders.map((a) => `${a.name} ${a.apps.length ? `works in ${list(a.apps)}` : "works without a connected app"}`)
    const gated = feeders.filter((a) => a.gated).length
    const blocked = feeders.filter((a) => a.state === "blocked")
    let s = `${countWord(feeders.length)} agent${feeders.length === 1 ? "" : "s"} feed${feeders.length === 1 ? "s" : ""} ${goal.objective}. ${list(parts)}.`
    if (gated > 0) s += gated === feeders.length ? " Their writes pause for your approval before they count." : ` ${countWord(gated)} of them pause${gated === 1 ? "s" : ""} for your approval before writing.`
    if (blocked.length > 0) s += ` ${list(blocked.map((a) => a.name))} ${blocked.length === 1 ? "is" : "are"} blocked right now.`
    return s
  }
  if (kind === "app") {
    const app = model.apps.find((p) => p.name === value)
    const names = (app?.agentIds ?? []).map((id) => byId.get(id)?.name).filter(Boolean) as string[]
    return names.length ? `${value} feeds ${list(names)}.` : `No agent uses ${value} yet.`
  }
  if (kind === "out") {
    const out = model.outputs.find((o) => o.name === value)
    if (!out) return ""
    const names = out.agentIds.map((id) => byId.get(id)?.name).filter(Boolean) as string[]
    const goalNames = out.goalIds.map((id) => model.goals.find((g) => g.id === id)?.objective).filter(Boolean) as string[]
    return `${value} comes from ${list(names)}.${out.gated ? " It writes to an app, so each batch waits for your approval." : " It is read only and never needs approval."}${goalNames.length ? ` It counts toward ${list(goalNames)}.` : " It is not tied to a goal yet."}`
  }
  const a = byId.get(value)
  if (!a) return ""
  if (!a.output) return `${a.name} has no work set up yet. Give it instructions and connect an app, and its path will appear here.`
  const goalNames = [...model.goalAgents.entries()].filter(([, ids]) => ids.includes(a.id)).map(([gid]) => model.goals.find((g) => g.id === gid)?.objective).filter(Boolean) as string[]
  let s = `${a.name} ${a.apps.length ? `pulls from ${list(a.apps)}` : "works without a connected app"}, produces ${a.output.toLowerCase()}${a.gated ? ", waits for your approval," : ""} and ${goalNames.length ? `counts toward ${list(goalNames)}.` : "is not tied to a goal yet."}`
  if (a.tasksToday > 0) s += ` It finished ${a.tasksToday} task${a.tasksToday === 1 ? "" : "s"} today.`
  const reason = blockedReason(a)
  if (reason) s += ` Right now it is blocked: ${reason.charAt(0).toLowerCase()}${reason.slice(1)}.`
  return s
}
