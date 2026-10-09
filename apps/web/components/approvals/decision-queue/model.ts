/**
 * Decision queue view model. Everything here is derived from GET /api/approvals
 * (workflow runs waiting on a human, chat connector writes and browser extension
 * writes). Nothing is invented: a field the backend does not send is left out.
 */

export type QueueTab = "pending" | "breached" | "approved" | "rejected"
export type ApprovalStatus = "pending" | "approved" | "rejected"
export type RiskLevel = "high" | "medium" | "low"

export type ApprovalPolicy = {
  source: "hitl" | "hitl_default" | "extension_confirm" | "approval_policy"
  id?: string | null
  name?: string | null
  missing?: boolean
  enabled?: boolean
  scope?: string | null
  actionKind?: string | null
  actionKinds?: string[]
  requiredApprovals?: number | null
  approverRoles?: string[]
}

export type ApprovalDecision = {
  approverName: string | null
  status: string
  comment: string | null
  decidedAt: string | null
}

export type ApprovalStep = {
  text: string
  /** Integration slug (hubspot, slack...) when the step names one. */
  app: string | null
  action: string | null
  access: "read" | "write"
}

export type Approval = {
  id: string
  title: string
  description: string
  type: string
  gateType: string
  environment: string
  priority: "high" | "medium" | "low"
  status: ApprovalStatus
  requestedBy: string
  requestedById: string | null
  requestedByEmail: string | null
  requestedAt: string | null
  reviewedBy: string | null
  reviewedAt: string | null
  reviewComment: string | null
  slaDeadline: string | null
  slaMinutesRemaining: number | null
  slaMinutes: number | null
  slaBreached: boolean
  requiredApprovals: number | null
  approvalsReceived: number | null
  policy: ApprovalPolicy | null
  decisions: ApprovalDecision[]
  /** What the agent asked to do, one row per planned step (GET /api/approvals `steps`). */
  steps: ApprovalStep[]
  /** Raw request as stored: run parameters for workflow runs, the staged context for writes. */
  rawRequest: Record<string, unknown>
  context: {
    entity: string
    action: string
    label: string | null
    integration: string | null
    tool: string | null
    args: Record<string, unknown> | null
    impact: string | null
    riskLevel: RiskLevel | null
    /** True when the backend scored risk from the steps instead of a stored score. */
    riskDerived: boolean
    approvalReason: string | null
    conversationId: string | null
    runId: string | null
    workflowId: string | null
    pageUrl: string | null
    source: string | null
  }
}

type Raw = Record<string, unknown>

function str(value: unknown): string | null {
  if (value === undefined || value === null) return null
  const out = String(value).trim()
  return out ? out : null
}

function num(value: unknown): number | null {
  if (value === undefined || value === null || value === "") return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function obj(value: unknown): Raw | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Raw) : null
}

function pick(input: Raw, ...keys: string[]): unknown {
  for (const key of keys) {
    if (input[key] !== undefined && input[key] !== null) return input[key]
  }
  return undefined
}

function riskOf(value: unknown): RiskLevel | null {
  const v = str(value)?.toLowerCase()
  if (v === "high" || v === "critical") return "high"
  if (v === "medium" || v === "moderate") return "medium"
  if (v === "low") return "low"
  return null
}

function formatRequester(value: string | null): string {
  if (!value || value === "system") return "System"
  if (/^[0-9a-f-]{36}$/i.test(value)) return "Team member"
  if (value.includes("@")) return value.split("@")[0].replace(/[._]/g, " ")
  return value
}

function normalizePolicy(raw: unknown): ApprovalPolicy | null {
  const p = obj(raw)
  if (!p) return null
  const source = str(p.source)
  if (
    source !== "hitl" &&
    source !== "hitl_default" &&
    source !== "extension_confirm" &&
    source !== "approval_policy"
  ) {
    return null
  }
  const list = (value: unknown) =>
    Array.isArray(value) ? value.map((v) => String(v)).filter(Boolean) : []
  return {
    source,
    id: str(p.id),
    name: str(p.name),
    missing: Boolean(p.missing),
    enabled: p.enabled === undefined ? undefined : Boolean(p.enabled),
    scope: str(p.scope),
    actionKind: str(pick(p, "action_kind", "actionKind")),
    actionKinds: list(pick(p, "action_kinds", "actionKinds")),
    requiredApprovals: num(pick(p, "required_approvals", "requiredApprovals")),
    approverRoles: list(pick(p, "approver_roles", "approverRoles")),
  }
}

export function normalizeApproval(input: Raw): Approval {
  const ctx = obj(input.context) ?? {}
  const status = str(input.status)
  const priority = str(input.priority)
  const gateType = str(pick(input, "gate_type", "gateType")) ?? str(ctx.gate_type) ?? ""
  const requestRaw = obj(input.request)
  const decisions = Array.isArray(input.decisions)
    ? (input.decisions as unknown[])
        .map((d) => obj(d))
        .filter((d): d is Raw => Boolean(d))
        .map((d) => ({
          approverName: str(pick(d, "approver_name", "approverName")),
          status: str(d.status) ?? "",
          comment: str(d.comment),
          decidedAt: str(pick(d, "decided_at", "decidedAt")),
        }))
    : []
  const tool = str(pick(ctx, "tool_name", "invoke_action")) ?? null
  return {
    id: String(input.id ?? ""),
    title: str(input.title) ?? "Approval request",
    description: str(input.description) ?? "",
    type: str(input.type) ?? "workflow",
    gateType,
    environment: str(input.environment) ?? "",
    priority: priority === "high" || priority === "low" ? priority : "medium",
    status: status === "approved" || status === "rejected" ? status : "pending",
    requestedBy: formatRequester(
      str(pick(input, "requestedByName", "requested_by_name", "requestedBy", "requested_by")),
    ),
    requestedById: str(pick(input, "requested_by", "requestedById")),
    requestedByEmail: (() => {
      const raw = str(pick(input, "requestedByEmail", "requested_by_email", "requested_by"))
      return raw && raw.includes("@") ? raw : null
    })(),
    requestedAt: str(pick(input, "requestedAt", "requested_at")),
    reviewedBy: (() => {
      const raw = str(pick(input, "reviewedByName", "reviewed_by_name"))
      return raw ? formatRequester(raw) : null
    })(),
    reviewedAt: str(pick(input, "reviewedAt", "reviewed_at")),
    reviewComment: str(pick(input, "review_comment", "reviewComment")),
    slaDeadline: str(pick(input, "slaDeadline", "sla_deadline")),
    slaMinutesRemaining: num(pick(input, "slaMinutesRemaining", "sla_minutes_remaining")),
    slaMinutes: num(pick(input, "slaMinutes", "sla_minutes")),
    slaBreached: Boolean(pick(input, "slaBreached", "sla_breached")),
    requiredApprovals: num(pick(input, "required_approvals", "requiredApprovals")),
    approvalsReceived: num(pick(input, "approvals_received", "approvalsReceived")),
    policy: normalizePolicy(input.policy),
    decisions,
    steps: Array.isArray(input.steps)
      ? (input.steps as unknown[])
          .map((row) => obj(row))
          .filter((row): row is Raw => Boolean(row))
          .map((row) => ({
            text: str(row.text) ?? str(row.action) ?? "Step",
            app: str(row.app),
            action: str(row.action),
            access: str(row.access) === "write" ? ("write" as const) : ("read" as const),
          }))
      : [],
    rawRequest: requestRaw ?? ctx,
    context: {
      entity: str(pick(ctx, "workflow_name", "entity")) ?? "",
      action: str(ctx.action) ?? "",
      label: str(ctx.label),
      integration: str(ctx.integration),
      tool,
      args: obj(ctx.args),
      impact: str(pick(ctx, "impact", "estimated_impact", "estimatedImpact")),
      riskLevel: riskOf(pick(ctx, "risk_level", "riskLevel")),
      riskDerived: Boolean(pick(ctx, "risk_derived", "riskDerived")),
      approvalReason: str(pick(ctx, "approval_reason", "approvalReason")),
      conversationId: str(pick(ctx, "conversation_id", "conversationId")),
      runId: str(pick(ctx, "run_id", "runId")),
      workflowId: str(pick(ctx, "workflow_id", "workflowId")),
      pageUrl: str(pick(ctx, "page_url", "pageUrl")),
      source: str(ctx.source),
    },
  }
}

export function normalizeApprovals(payload: unknown): Approval[] {
  const model = obj(payload)
  if (!model) return []
  const raw =
    (Array.isArray(model.approvals) ? model.approvals : null) ??
    (Array.isArray(model.data) ? model.data : null) ??
    (Array.isArray(model.items) ? model.items : null)
  if (!raw) return []
  return raw
    .map((item) => obj(item))
    .filter((item): item is Raw => Boolean(item))
    .map(normalizeApproval)
    .filter((item) => item.id.length > 0)
}

/* ------------------------------------------------------------------ */
/* Labels                                                              */
/* ------------------------------------------------------------------ */

const WORKFLOW_GATES = new Set(["execute", "chat_orchestration_plan"])
const EXTENSION_GATES = new Set(["browser_extension_write", "browser_extension_workflow"])

export function isWorkflowGate(a: Approval) {
  return WORKFLOW_GATES.has(a.gateType) || (!a.gateType && a.type === "workflow")
}

export function isExtensionGate(a: Approval) {
  return EXTENSION_GATES.has(a.gateType) || a.type.startsWith("extension_")
}

export function typeLabel(a: Approval): string {
  if (a.gateType === "browser_extension_workflow") return "Extension workflow"
  if (isExtensionGate(a)) return "Extension write"
  if (a.gateType === "chat_orchestration_plan") return "Chat plan"
  if (isWorkflowGate(a)) return "Workflow run"
  return "Connector write"
}

export function sourcePhrase(a: Approval): string {
  if (isExtensionGate(a)) return " from the browser extension"
  if (a.gateType === "chat_connector_write" || a.gateType === "chat_orchestration_plan") return " from chat"
  return ""
}

export function environmentLabel(env: string): string | null {
  if (!env) return null
  return env.charAt(0).toUpperCase() + env.slice(1)
}

export function humanize(key: string): string {
  const spaced = key.replace(/[_.-]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2").trim().toLowerCase()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** Impact text is a sentence: keep its words, capitalise only the first letter. */
export function sentenceCase(value: string): string {
  const text = value.trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

/* ------------------------------------------------------------------ */
/* Time                                                                */
/* ------------------------------------------------------------------ */

export function parseTime(value: string | null): number | null {
  if (!value) return null
  const t = new Date(value).getTime()
  return Number.isNaN(t) ? null : t
}

export function formatDuration(ms: number): string {
  const mins = Math.max(0, Math.floor(ms / 60000))
  if (mins < 1) return "less than a minute"
  if (mins < 60) return `${mins} min`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} h`
  const days = Math.floor(hours / 24)
  return `${days} ${days === 1 ? "day" : "days"}`
}

export function formatDate(value: string | null, now = Date.now()): string | null {
  const t = parseTime(value)
  if (t == null) return null
  const d = new Date(t)
  const sameDay = new Date(now).toDateString() === d.toDateString()
  const date = d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
  if (sameDay) {
    return `Today, ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`
  }
  return date
}

export function isPastSla(a: Approval, now = Date.now()): boolean {
  if (a.status !== "pending") return false
  if (a.slaBreached) return true
  const deadline = parseTime(a.slaDeadline)
  return deadline != null && deadline < now
}

/** "SLA breached · waiting 3 days" / "Due in 2 h · waiting 40 min" */
export function slaLine(a: Approval, now = Date.now()): { text: string; breached: boolean } | null {
  if (a.status !== "pending") return null
  const requested = parseTime(a.requestedAt)
  const waiting = requested != null ? `waiting ${formatDuration(now - requested)}` : null
  const deadline = parseTime(a.slaDeadline)
  if (isPastSla(a, now)) {
    return { text: ["SLA breached", waiting].filter(Boolean).join(" · "), breached: true }
  }
  if (deadline != null) {
    return { text: [`Due in ${formatDuration(deadline - now)}`, waiting].filter(Boolean).join(" · "), breached: false }
  }
  return waiting ? { text: waiting.charAt(0).toUpperCase() + waiting.slice(1), breached: false } : null
}

/** Headline under the page title, from the live counts only. */
export function summarySentence(waiting: number, breached: number): { lead: string; rest: string } {
  if (waiting === 0) {
    return { lead: "Nothing is waiting on you", rest: ". New requests appear here the moment an agent pauses." }
  }
  const lead = `${waiting} waiting on you`
  let sla: string
  if (breached === 0) sla = waiting === 1 ? ", and it is within its SLA." : ", all within their SLA."
  else if (breached === waiting) sla = waiting === 1 ? ", and it is past its SLA." : ", all past their SLA."
  else sla = `, ${breached} past ${breached === 1 ? "its" : "their"} SLA.`
  return { lead, rest: `${sla} The paused work continues once you decide.` }
}

/* ------------------------------------------------------------------ */
/* Detail content                                                      */
/* ------------------------------------------------------------------ */

export type DetailRow = { term: string; value: string; mono?: boolean; href?: string }

function displayValue(value: unknown): string | null {
  if (value === null || value === undefined) return null
  if (typeof value === "string") return value.trim() ? value : null
  if (typeof value === "number" || typeof value === "boolean") return value === true ? "Yes" : value === false ? "No" : String(value)
  if (Array.isArray(value)) {
    const parts = value.map((v) => displayValue(v)).filter(Boolean)
    return parts.length ? parts.join(", ") : null
  }
  try {
    const json = JSON.stringify(value)
    return json.length > 120 ? `${json.slice(0, 117)}...` : json
  } catch {
    return null
  }
}

const HIDDEN_ARG_KEYS = new Set(["page_url", "extension_page_url", "org_id", "user_id", "conversation_id"])

export function whatWillHappen(a: Approval): DetailRow[] {
  const rows: DetailRow[] = []
  const ctx = a.context
  const env = environmentLabel(a.environment)
  if (isWorkflowGate(a)) {
    rows.push({ term: "Action", value: a.gateType === "chat_orchestration_plan" ? "Run the chat plan" : "Run the workflow" })
    if (ctx.entity) {
      rows.push({
        term: "Workflow",
        value: ctx.entity,
        href: ctx.workflowId ? `/workflows/${encodeURIComponent(ctx.workflowId)}` : undefined,
      })
    }
    if (env) rows.push({ term: "Environment", value: env })
    if (a.requiredApprovals) {
      const got = a.approvalsReceived ?? 0
      rows.push({
        term: "Approvals needed",
        value: a.requiredApprovals === 1 ? "1" : `${a.requiredApprovals} (${got} received)`,
      })
    }
  } else {
    const action = ctx.label || ctx.action
    if (action) rows.push({ term: "Action", value: action })
    const app = ctx.integration ? titleCase(ctx.integration) : ctx.entity
    if (app || env) rows.push({ term: "App", value: [app, env].filter(Boolean).join(" · ") })
    if (ctx.tool) rows.push({ term: "Tool", value: ctx.tool, mono: true })
    const args = ctx.args ?? {}
    for (const [key, value] of Object.entries(args)) {
      if (HIDDEN_ARG_KEYS.has(key)) continue
      const shown = displayValue(value)
      if (shown) rows.push({ term: humanize(key), value: shown })
      if (rows.length >= 9) break
    }
    if (ctx.pageUrl) {
      let host = ctx.pageUrl
      try {
        host = new URL(ctx.pageUrl).hostname
      } catch {
        /* keep raw */
      }
      rows.push({ term: "Proposed on", value: host })
    }
  }
  if (ctx.impact) rows.push({ term: "Impact", value: sentenceCase(ctx.impact) })
  if (ctx.runId) rows.push({ term: "Run", value: "Open the run", href: `/runs/${encodeURIComponent(ctx.runId)}` })
  return rows
}

const SCOPE_PHRASE: Record<string, string> = {
  org: "the whole workspace",
  department: "one department",
  user: "one person",
}

function rolesPhrase(roles: string[] | undefined): string | null {
  if (!roles || roles.length === 0) return null
  const named = roles.map((r) => r.toLowerCase())
  if (named.length === 1) return `an ${named[0]}`.replace(/^an ([^aeiou])/, "a $1")
  return `${named.slice(0, -1).join(", ")} or ${named[named.length - 1]}`
}

export function policyCopy(a: Approval): { title: string; body: string } | null {
  const p = a.policy
  if (!p) return null
  const kind = p.actionKind || "write"
  const needs = (n?: number | null) => (n && n > 1 ? `${n} approvals` : "1 approval")
  const roles = rolesPhrase(p.approverRoles)
  if (p.source === "hitl") {
    if (p.missing) {
      return {
        title: "Paused by a Human-in-the-loop policy that no longer exists.",
        body: "The policy was removed after this request arrived. The request still needs a decision.",
      }
    }
    const kinds = p.actionKinds && p.actionKinds.length ? p.actionKinds.join(", ") : kind
    return {
      title: `Policy: ${p.name ?? "Human-in-the-loop policy"}.`,
      body: [
        `Set in Human-in-the-loop. Covers ${kinds} actions for ${SCOPE_PHRASE[p.scope ?? "org"] ?? "this workspace"}.`,
        `Needs ${needs(p.requiredApprovals)}${roles ? ` from ${roles}` : ""}.`,
        p.enabled === false ? "The policy has since been turned off." : null,
      ]
        .filter(Boolean)
        .join(" "),
    }
  }
  if (p.source === "hitl_default") {
    return {
      title: `No Human-in-the-loop policy covers this ${kind}, so it waits for an admin.`,
      body: "Writes and deletes always need approval unless a policy says otherwise.",
    }
  }
  if (p.source === "extension_confirm") {
    return {
      title: "Writes proposed in the browser extension wait for a confirmation.",
      body: "The person who proposed it or an admin can decide. It runs as the person who proposed it.",
    }
  }
  const scopeTitle =
    p.scope === "workflow"
      ? `Policy: this workflow needs ${needs(p.requiredApprovals)} before it runs.`
      : p.scope === "org"
        ? `Policy: workflow runs in this workspace need ${needs(p.requiredApprovals)}.`
        : `Workflow runs need ${needs(p.requiredApprovals)} by default.`
  return {
    title: scopeTitle,
    body: roles ? `Approvers: ${p.approverRoles!.join(", ")}.` : "Approvers: workspace admins.",
  }
}

export type ActivityEvent = { key: string; title: string; detail: string | null; tone: "muted" | "red" | "amber" | "green" }

export function activity(a: Approval, now = Date.now()): ActivityEvent[] {
  const events: ActivityEvent[] = []
  events.push({
    key: "requested",
    title: `Requested by ${a.requestedBy}${sourcePhrase(a)}`,
    detail: formatDate(a.requestedAt, now),
    tone: "muted",
  })
  const deadline = parseTime(a.slaDeadline)
  const reviewed = parseTime(a.reviewedAt)
  const passedSla =
    deadline != null &&
    deadline < now &&
    (a.status === "pending" || (reviewed != null && reviewed > deadline))
  if (passedSla) {
    events.push({
      key: "sla",
      title: a.status === "pending" ? "Passed its SLA with no decision" : "Passed its SLA before a decision",
      detail: a.status === "pending" ? "Flagged in Past SLA" : formatDate(a.slaDeadline, now),
      tone: "red",
    })
  }
  if (a.decisions.length) {
    for (const [i, d] of a.decisions.entries()) {
      const verb = d.status === "rejected" ? "Rejected" : "Approved"
      events.push({
        key: `decision-${i}`,
        title: `${verb}${d.approverName ? ` by ${d.approverName}` : ""}`,
        detail: [formatDate(d.decidedAt, now), d.comment ? `"${d.comment}"` : null].filter(Boolean).join(" · ") || null,
        tone: d.status === "rejected" ? "red" : "green",
      })
    }
  } else if (a.status !== "pending") {
    events.push({
      key: "decided",
      title: `${a.status === "rejected" ? "Rejected" : "Approved"}${a.reviewedBy ? ` by ${a.reviewedBy}` : ""}`,
      detail: formatDate(a.reviewedAt, now),
      tone: a.status === "rejected" ? "red" : "green",
    })
  }
  if (a.status === "pending") {
    events.push({ key: "waiting", title: "Waiting on you", detail: "Now", tone: "amber" })
  }
  return events
}

export function lockNote(a: Approval): string {
  if (isExtensionGate(a)) {
    return "Approving runs it through the same confirmation the extension uses with its server issued token, as the person who proposed it."
  }
  if (a.gateType === "chat_connector_write") {
    return "Approving runs the staged write through the same gate used for chat confirmations."
  }
  return "Approving records your decision against your admin role and resumes the paused run."
}

export function matchesQuery(a: Approval, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return [
    a.title,
    a.description,
    a.requestedBy,
    a.context.entity,
    a.context.action,
    a.context.label,
    a.context.integration,
    a.context.tool,
    typeLabel(a),
  ]
    .filter(Boolean)
    .some((v) => String(v).toLowerCase().includes(q))
}

/** "Member, Jul 18, 2026" / "Dana and Sam, Jul 15, 2026" / "Waiting on you". */
export function decidedByLine(a: Approval, now = Date.now()): string {
  if (a.status === "pending") {
    const got = a.approvalsReceived ?? 0
    const need = a.requiredApprovals ?? a.policy?.requiredApprovals ?? null
    return need && need > 1 ? `Waiting on you · ${got} of ${need} approvals` : "Waiting on you"
  }
  const names = a.decisions.length
    ? [...new Set(a.decisions.filter((d) => d.status === a.status).map((d) => d.approverName).filter(Boolean))]
    : a.reviewedBy
      ? [a.reviewedBy]
      : []
  const who = names.length === 0 ? "Not recorded" : names.length === 1 ? String(names[0]) : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
  const when = formatDate(a.reviewedAt, now)
  return when ? `${who}, ${when}` : who
}

/** One line naming the rule that made the request wait. */
export function policyLine(a: Approval): string {
  const p = a.policy
  if (!p) return a.context.approvalReason ?? "Not reported"
  const n = p.requiredApprovals && p.requiredApprovals > 1 ? `${p.requiredApprovals} approvals` : "one approval"
  if (p.source === "hitl") return p.missing ? "A policy that no longer exists" : p.name ?? `Human-in-the-loop: ${n}`
  if (p.source === "hitl_default") return `Writes need ${n} by default`
  if (p.source === "extension_confirm") return "Extension writes need a confirmation"
  if (a.gateType === "chat_orchestration_plan") return `Chat plans need ${n}`
  if (p.scope === "workflow") return `This workflow needs ${n}`
  if (p.scope === "org") return `Workflow runs need ${n}`
  return `Workflow runs need ${n} by default`
}

export function riskLabel(level: RiskLevel | null): string {
  if (!level) return "Not scored"
  return `${level.charAt(0).toUpperCase()}${level.slice(1)} risk`
}
