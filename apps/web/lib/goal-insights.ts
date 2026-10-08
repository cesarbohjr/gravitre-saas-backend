/**
 * Pure helpers behind the Goals list and the New goal flow. Everything here is
 * derived from a goal's stored fields (goals table) or a real assignment; when a
 * value is not stored it comes back null so the UI can say "Not reported".
 */
import type { DemoAssignment } from "@/lib/demo-assignments"
import type { GoalRecord, GoalStatus } from "@/lib/goals-list"

export const GOAL_DEPARTMENTS = [
  { id: "sales", label: "Sales" },
  { id: "marketing", label: "Marketing" },
  { id: "operations", label: "Operations" },
  { id: "finance", label: "Finance" },
  { id: "support", label: "Support" },
  { id: "engineering", label: "Engineering" },
] as const

export type GoalDepartmentId = (typeof GOAL_DEPARTMENTS)[number]["id"]

export const GOAL_PRIORITIES = ["low", "medium", "high", "urgent"] as const
export const GOAL_CADENCES = ["once", "weekly", "monthly", "ongoing"] as const

export const GOAL_STATUS_TABS: Array<{
  id: GoalStatus
  label: string
  heading: string
  hint: string
}> = [
  { id: "active", label: "In motion", heading: "In motion", hint: "Every run moves the number, with evidence" },
  { id: "draft", label: "Draft", heading: "Drafts", hint: "A draft becomes active once you approve its plan" },
  { id: "paused", label: "Paused", heading: "Paused", hint: "Paused goals keep their plan until you resume them" },
  { id: "completed", label: "Completed", heading: "Completed", hint: "Finished goals and their results" },
  { id: "cancelled", label: "Cancelled", heading: "Cancelled", hint: "Cancelled goals stay here for reference" },
]

export const KNOWN_STATUSES: GoalStatus[] = GOAL_STATUS_TABS.map((t) => t.id)

export function goalStatusOf(goal: GoalRecord): GoalStatus | "unreported" {
  return KNOWN_STATUSES.includes(goal.status) ? goal.status : "unreported"
}

/** Normalises a stored department ("Sales", "sales ops") to a known id, or null. */
export function departmentId(value?: string | null): GoalDepartmentId | null {
  const text = (value ?? "").trim().toLowerCase()
  if (!text) return null
  const exact = GOAL_DEPARTMENTS.find((d) => d.id === text || d.label.toLowerCase() === text)
  if (exact) return exact.id
  const partial = GOAL_DEPARTMENTS.find((d) => text.includes(d.id))
  return partial ? partial.id : null
}

export function departmentLabel(value?: string | null): string | null {
  const id = departmentId(value)
  if (id) return GOAL_DEPARTMENTS.find((d) => d.id === id)!.label
  const text = (value ?? "").trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : null
}

export function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value
}

export function cadenceLabel(frequency?: string | null): string {
  switch ((frequency ?? "").toLowerCase()) {
    case "once":
      return "Runs once"
    case "daily":
      return "Runs daily"
    case "weekly":
      return "Runs weekly"
    case "monthly":
      return "Runs monthly"
    case "ongoing":
      return "Runs continuously"
    default:
      return "Cadence not set"
  }
}

const PRIORITY_ORDER = ["urgent", "high", "medium", "low"]
export function priorityRank(priority?: string | null): number {
  const index = PRIORITY_ORDER.indexOf((priority ?? "").toLowerCase())
  return index < 0 ? PRIORITY_ORDER.length : index
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function finite(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

export interface GoalMetrics {
  /** What is counted, e.g. "MSP leads added to HubSpot". */
  metric: string | null
  start: number | null
  target: number | null
  /** ISO date (yyyy-mm-dd) the goal is due, when set. */
  dueDate: string | null
  /** Set when the goal carries an objective contract on a verified metric. */
  isObjective: boolean
  ownerName: string | null
}

/** Reads the measure fields the New goal flow writes into success_metrics. */
export function goalMetrics(goal: GoalRecord): GoalMetrics {
  const sm = record(goal.successMetrics)
  const contract = record(sm.contract)
  const owner = record(sm.owner)
  const isObjective = Object.keys(contract).length > 0
  return {
    metric: text(sm.metric) ?? text(sm.primary) ?? text(contract.metricLabel) ?? text(contract.metricKey)?.replace(/_/g, " ") ?? null,
    start: finite(sm.start),
    target: finite(sm.target) ?? finite(contract.target),
    dueDate: text(sm.dueDate) ?? text(sm.due_date),
    isObjective,
    ownerName: text(owner.name),
  }
}

export interface GoalMeasure {
  current: number | null
  /** Current value is the stored starting value because nothing has run yet. */
  currentIsStart: boolean
  target: number | null
  metric: string | null
  /** 0..100 when both current and target are known; null otherwise. */
  percent: number | null
  stateLabel: string
  dueLabel: string
}

export function formatShortDate(value?: string | null): string | null {
  if (!value) return null
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T00:00:00`) : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

/**
 * Current value vs target. `reportedCurrent` is a verified value from the
 * objective progress endpoint; without it only an unstarted draft shows its
 * starting value, everything else stays unreported.
 */
export function goalMeasure(goal: GoalRecord, reportedCurrent: number | null = null): GoalMeasure {
  const m = goalMetrics(goal)
  const status = goalStatusOf(goal)
  let current = reportedCurrent
  let currentIsStart = false
  if (current === null && status === "draft" && m.start !== null) {
    current = m.start
    currentIsStart = true
  }
  let percent: number | null = null
  if (current !== null && m.target !== null) {
    const base = m.start ?? 0
    const span = m.target - base
    percent = span === 0 ? (current >= m.target ? 100 : 0) : ((current - base) / span) * 100
    percent = Math.max(0, Math.min(100, Math.round(percent)))
  }
  const stateLabel =
    status === "completed"
      ? "Completed"
      : status === "draft"
        ? "Not started"
        : status === "paused"
          ? "Paused"
          : status === "cancelled"
            ? "Cancelled"
            : percent !== null
              ? `${percent}% of target`
              : "Progress not reported"
  const due = formatShortDate(m.dueDate)
  return {
    current,
    currentIsStart,
    target: m.target,
    metric: m.metric,
    percent,
    stateLabel,
    dueLabel: due ? `Due ${due}` : "Due date not set",
  }
}

export interface SetupItem {
  label: string
  done: boolean
}

/** The "Finish setup" checklist, one item per real goal field. */
export function goalSetupChecklist(goal: GoalRecord): SetupItem[] {
  const m = goalMetrics(goal)
  const status = goalStatusOf(goal)
  return [
    { label: "Write the outcome", done: Boolean(goal.objective?.trim()) },
    { label: "Pick a department", done: Boolean(goal.department?.trim()) },
    { label: "Set the target date", done: Boolean(m.dueDate) },
    {
      label: "Approve Gravitre's plan",
      done: status === "active" || status === "paused" || status === "completed",
    },
  ]
}

const STOPWORDS = new Set(
  "the and for with into from that this our your their more less than per by of to in on at a an get make grow reduce increase every each all new goal goals within one day days week weeks month months quarter year business".split(
    " ",
  ),
)

export function significantTokens(value: string): string[] {
  return [
    ...new Set(
      value
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter((t) => t.length >= 3 && !STOPWORDS.has(t) && !/^\d+$/.test(t))
        .map((t) => (t.length > 4 && t.endsWith("s") ? t.slice(0, -1) : t)),
    ),
  ]
}

/**
 * The closest real assignment for a goal: an agent job whose title or brief
 * shares the goal objective's key terms (at least two, or the only one when the
 * objective has a single key term). Most overlap wins, newest breaks ties.
 */
export function findRelatedAssignment(
  goal: GoalRecord,
  assignments: DemoAssignment[],
): DemoAssignment | null {
  const goalTokens = significantTokens(`${goal.objective ?? ""}`)
  if (goalTokens.length === 0) return null
  const needed = Math.min(2, goalTokens.length)
  let best: { item: DemoAssignment; score: number; at: number } | null = null
  for (const item of assignments) {
    const tokens = new Set(significantTokens(`${item.title} ${item.brief}`))
    const score = goalTokens.filter((t) => tokens.has(t)).length
    if (score < needed) continue
    const at = Date.parse(item.createdAtIso ?? item.createdAt ?? "") || 0
    if (!best || score > best.score || (score === best.score && at > best.at)) {
      best = { item, score, at }
    }
  }
  return best?.item ?? null
}

/** One plain sentence about the related assignment, built from its own record. */
export function relatedWorkSummary(item: DemoAssignment): string {
  const when = formatShortDate(item.createdAtIso ?? item.createdAt)
  const name = item.agent.name && item.agent.name !== "Agent" ? item.agent.name : "An agent"
  const opener = `${name} worked on "${item.title}"${when ? ` on ${when}` : ""}.`
  const clip = (v: string) => (v.length > 180 ? `${v.slice(0, 177).trimEnd()}...` : v)
  switch (item.status) {
    case "failed":
      return item.blocker ? `${opener} It stopped: ${clip(item.blocker)}` : `${opener} It did not finish.`
    case "needs_approval":
      return `${opener} It is waiting for your decision.`
    case "running":
      return `${opener} It is still running.`
    case "completed":
      return item.resultSummary ? `${opener} ${clip(item.resultSummary)}` : `${opener} It finished.`
    default:
      return `${opener} It has not started yet.`
  }
}

export type GoalStrengthCheck = { id: string; label: string; ok: boolean; note: string }

const DATE_WORDS =
  /\b(by|before|until|end of|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|q[1-4]|week|month|quarter|year|today|tomorrow)\b/i

/** "Is it a strong goal?" checks, computed from the outcome text and measure fields. */
export function goalStrengthChecks(input: {
  objective: string
  target?: string
  dueDate?: string
}): GoalStrengthCheck[] {
  const t = input.objective.trim()
  const specific = t.split(/\s+/).filter(Boolean).length >= 3
  const measurable = /\d/.test(t) || Boolean(input.target?.trim())
  const timeBound = DATE_WORDS.test(t) || Boolean(input.dueDate?.trim())
  return [
    {
      id: "specific",
      label: "Specific.",
      ok: specific,
      note: specific ? "Clear about what changes." : "Say what should change.",
    },
    {
      id: "measurable",
      label: "Measurable.",
      ok: measurable,
      note: measurable ? "Has a number to track." : "Add a number, like 100.",
    },
    {
      id: "time",
      label: "Time bound.",
      ok: timeBound,
      note: timeBound ? "Has a deadline." : "Add a date, like by Dec 31.",
    },
  ]
}

export interface GoalTemplate {
  id: string
  department: GoalDepartmentId
  objective: string
  metric: string
  illustration: "goal-template-marketing" | "goal-template-finance" | "goal-template-support"
}

/** Starting points for the New goal flow. They prefill text only, never numbers. */
export const GOAL_TEMPLATES: GoalTemplate[] = [
  {
    id: "marketing-signups",
    department: "marketing",
    objective: "Grow qualified signups from content",
    metric: "Qualified signups from content",
    illustration: "goal-template-marketing",
  },
  {
    id: "finance-overdue",
    department: "finance",
    objective: "Reduce overdue invoices",
    metric: "Overdue invoices",
    illustration: "goal-template-finance",
  },
  {
    id: "support-response",
    department: "support",
    objective: "Answer every ticket within one business day",
    metric: "Tickets answered within one business day",
    illustration: "goal-template-support",
  },
]

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?"
}
