/**
 * Impact page model: turns the agent ROI report, the intelligence snapshot and
 * the connector list into what the page shows. Pure functions only, so the
 * "a dash means no evidence, never zero" rules are testable.
 */
import type { IntelligencePageContextResponse, OutcomeAttributionPath } from "@/lib/api"
import type { AgentRoiMetric, AgentRoiReport, AgentRoiRow, Connector } from "@/types/api"

export const IMPACT_PERIODS = [7, 30, 90] as const
export type ImpactPeriod = (typeof IMPACT_PERIODS)[number]

export const UNASSIGNED_AGENT_ID = "unassigned"

/** How sure Gravitre is about a number. */
export type Certainty = "measured" | "estimated" | "none"

export const CERTAINTY_LABEL: Record<Certainty, string> = {
  measured: "Measured",
  estimated: "Estimated",
  none: "No evidence yet",
}

export function metricNumber(metric: AgentRoiMetric | null | undefined): number | null {
  if (!metric) return null
  if (metric.provenance === "not_configured" || metric.provenance === "insufficient_data") return null
  if (metric.value == null || metric.value === "") return null
  const n = typeof metric.value === "number" ? metric.value : Number(metric.value)
  return Number.isFinite(n) ? n : null
}

export function metricCertainty(metric: AgentRoiMetric | null | undefined): Certainty {
  if (metricNumber(metric) == null) return "none"
  switch (metric?.provenance) {
    case "measured":
    case "operational":
      return "measured"
    default:
      return "estimated"
  }
}

const DASH = "—"

export function formatUsd(value: number | null): string {
  if (value == null) return DASH
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: value >= 1000 ? 0 : 2,
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value)
}

export function formatHours(value: number | null): string {
  if (value == null) return DASH
  if (value === 0) return "0 h"
  if (value < 10) return `${Number(value.toFixed(1))} h`
  return `${Math.round(value).toLocaleString("en-US")} h`
}

export function formatCount(value: number | null): string {
  if (value == null) return DASH
  return Math.round(value).toLocaleString("en-US")
}

export function formatMultiple(value: number | null): string {
  if (value == null) return DASH
  return `${value.toFixed(value >= 10 ? 0 : 1)}×`
}

export type ImpactTotals = {
  spent: number | null
  spentCertainty: Certainty
  tasks: number | null
  tasksCertainty: Certainty
  hours: number | null
  hoursCertainty: Certainty
  revenue: number | null
  revenueCertainty: Certainty
  roi: number | null
  roiCertainty: Certainty
  unassignedCost: number
}

export function impactTotals(report: AgentRoiReport | null | undefined): ImpactTotals {
  const t = report?.orgTotals
  const unassigned = report?.agents.find((a) => a.agentId === UNASSIGNED_AGENT_ID)
  return {
    spent: metricNumber(t?.agentCostUsd),
    spentCertainty: metricCertainty(t?.agentCostUsd),
    tasks: metricNumber(t?.tasksCompleted),
    tasksCertainty: metricCertainty(t?.tasksCompleted),
    hours: metricNumber(t?.estimatedHoursSaved),
    hoursCertainty: metricCertainty(t?.estimatedHoursSaved),
    revenue: metricNumber(t?.revenueInfluencedUsd),
    revenueCertainty: metricCertainty(t?.revenueInfluencedUsd),
    roi: metricNumber(t?.roiMultiple),
    roiCertainty: metricCertainty(t?.roiMultiple),
    unassignedCost: metricNumber(unassigned?.agentCostUsd) ?? 0,
  }
}

/** Why Return has no value yet, in the design's words. */
export function returnMissingReason(totals: ImpactTotals): string {
  if (!totals.tasks) return "Needs one finished task"
  if (totals.spent == null) return "Needs measured spend"
  return "Needs time saved"
}

/** Known agents first (as the API orders them), the Unassigned row last. */
export function orderAgentRows(rows: AgentRoiRow[] | undefined): AgentRoiRow[] {
  rows = rows ?? []
  return [
    ...rows.filter((r) => r.agentId !== UNASSIGNED_AGENT_ID),
    ...rows.filter((r) => r.agentId === UNASSIGNED_AGENT_ID),
  ]
}

type SnapshotAgent = IntelligencePageContextResponse["snapshot"]["agents"][number]

export type AgentStatusLine = { text: string; tone: "muted" | "danger" | "warning" | "live" }

export function agentStatusLine(row: AgentRoiRow, agent: SnapshotAgent | undefined): AgentStatusLine {
  if (row.agentId === UNASSIGNED_AGENT_ID) {
    return { text: "Spend with no agent attached", tone: "warning" }
  }
  const tasks = metricNumber(row.tasksCompleted) ?? 0
  const activity = tasks > 0 ? "ran this period" : "no runs this period"
  if (agent?.isCurrentlyRunning) return { text: `Running now · ${activity}`, tone: "live" }
  if (agent?.configuredStatus === "error") return { text: "Blocked · needs attention", tone: "danger" }
  if (agent?.configuredStatus === "active" || agent?.configuredStatus === "processing") {
    return { text: `Active · ${activity}`, tone: "muted" }
  }
  if (agent) return { text: `Idle · ${activity}`, tone: "muted" }
  return { text: tasks > 0 ? "Ran this period" : "No runs this period", tone: "muted" }
}

/** Connector statuses that need someone to sign in. Shared with Reports' governance count. */
const NEEDS_SIGN_IN = new Set(["pending", "pending_auth", "needs_connection", "auth_expired"])
/** Sign-in problems plus broken connections; the first-result checklist offers a reconnect for either. */
const NEEDS_RECONNECT = new Set([...NEEDS_SIGN_IN, "error", "misconfigured"])
const CONNECTED = new Set(["active", "healthy", "connected", "syncing"])

export function connectorNeedsSignIn(c: Connector): boolean {
  return NEEDS_SIGN_IN.has(String(c.status ?? "").toLowerCase())
}

export type FirstResultStep = {
  id: "connect" | "revenue" | "task"
  title: string
  detail: string
  done: boolean
  href: string
  actionLabel: string
}

export function firstResultSteps({
  connectors,
  totals,
  routes,
}: {
  connectors: Connector[] | null | undefined
  totals: ImpactTotals
  routes: { connectors: string; plays: string; agents: string }
}): FirstResultStep[] {
  const list = connectors ?? []
  const broken = list.find((c) => NEEDS_RECONNECT.has(String(c.status ?? "").toLowerCase()))
  const connected = list.filter((c) => CONNECTED.has(String(c.status ?? "").toLowerCase()))

  const connect: FirstResultStep = broken
    ? {
        id: "connect",
        title: `Reconnect ${broken.name || broken.vendor}`,
        detail: "Agents that read it are blocked until it signs in again",
        done: false,
        href: `${routes.connectors}/${encodeURIComponent(broken.id)}`,
        actionLabel: `Reconnect ${broken.name || broken.vendor}`,
      }
    : connected.length > 0
      ? {
          id: "connect",
          title: "Keep your connections signed in",
          detail: `${connected.length} connected, none need sign-in`,
          done: true,
          href: routes.connectors,
          actionLabel: "Open connections",
        }
      : {
          id: "connect",
          title: "Connect your CRM",
          detail: "Agents need a signed-in source to act on",
          done: false,
          href: routes.connectors,
          actionLabel: "Connect a source",
        }

  const revenueOn = totals.revenueCertainty !== "none"
  const revenue: FirstResultStep = {
    id: "revenue",
    title: "Turn on revenue tracking",
    detail: revenueOn
      ? "Verified deal values are being counted"
      : "Counts won deal values verified against your CRM",
    done: revenueOn,
    href: routes.plays,
    actionLabel: "Turn on revenue tracking",
  }

  const taskDone = (totals.tasks ?? 0) > 0
  const task: FirstResultStep = {
    id: "task",
    title: "Let an agent finish a task",
    detail: taskDone
      ? `${formatCount(totals.tasks)} finished this period`
      : "Then time saved and return fill in",
    done: taskDone,
    href: routes.agents,
    actionLabel: "Open agents",
  }

  return [connect, revenue, task]
}

export type OutcomeProgress = {
  headlinePath: OutcomeAttributionPath
  present: number
  total: number
  segments: boolean[]
  summary: string
}

const AGENT_STEP_KINDS = new Set(["agent_workflow", "action"])

/** Steps in every outcome path (backend OUTCOME_PATH_STEP_KINDS). Drives the empty trail bar. */
export const OUTCOME_PATH_STEP_COUNT = 8

export function outcomeProgress(path: OutcomeAttributionPath | null | undefined): OutcomeProgress | null {
  if (!path || path.steps.length === 0) return null
  const segments = path.steps.map((s) => s.present)
  const present = segments.filter(Boolean).length
  const total = segments.length
  const lead = `${present} of ${total} ${total === 1 ? "step has" : "steps have"} evidence.`
  let tail: string
  if (present === total) {
    tail = "Every step is backed by a record."
  } else if (!path.steps.some((s) => s.present && AGENT_STEP_KINDS.has(s.kind))) {
    tail = "The trail stops before any agent acted."
  } else {
    const firstMissing = path.steps.find((s) => !s.present)
    tail = firstMissing ? `The trail stops at ${firstMissing.title.toLowerCase()}.` : ""
  }
  return { headlinePath: path, present, total, segments, summary: `${lead} ${tail}`.trim() }
}

function csvCell(value: string | number | null): string {
  const s = value == null ? "" : String(value)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

/**
 * CSV of exactly what the page shows for the period. Blank cells mean no
 * evidence (never zero); a certainty column says how sure each total is.
 */
export function impactCsv({
  report,
  period,
  agentNames,
}: {
  report: AgentRoiReport
  period: ImpactPeriod
  agentNames?: (row: AgentRoiRow) => string
}): string {
  const totals = impactTotals(report)
  const lines: string[] = []
  lines.push(["Section", "Name", "Value", "Certainty"].join(","))
  lines.push(["Period", `Last ${period} days`, `${report.periodStart} to ${report.periodEnd}`, ""].map(csvCell).join(","))
  const totalRows: Array<[string, number | null, Certainty]> = [
    ["Spent (USD)", totals.spent, totals.spentCertainty],
    ["Tasks done", totals.tasks, totals.tasksCertainty],
    ["Time saved (hours)", totals.hours, totals.hoursCertainty],
    ["Revenue influenced (USD)", totals.revenue, totals.revenueCertainty],
    ["Return (estimated labor value / cost)", totals.roi, totals.roiCertainty],
  ]
  for (const [name, value, certainty] of totalRows) {
    lines.push(["From spend to value", name, value, CERTAINTY_LABEL[certainty]].map(csvCell).join(","))
  }
  lines.push("")
  lines.push(["Agent", "Tasks", "Time saved (hours)", "Revenue (USD)", "Cost (USD)"].join(","))
  for (const row of orderAgentRows(report.agents)) {
    lines.push(
      [
        agentNames ? agentNames(row) : row.agentName,
        metricNumber(row.tasksCompleted),
        metricNumber(row.estimatedHoursSaved),
        metricNumber(row.revenueInfluencedUsd),
        metricNumber(row.agentCostUsd),
      ]
        .map(csvCell)
        .join(","),
    )
  }
  return `${lines.join("\n")}\n`
}
