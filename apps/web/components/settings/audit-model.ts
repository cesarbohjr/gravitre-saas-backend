/**
 * Pure helpers for the Audit trail page: row labels, the expandable metadata
 * tiles (only keys the event actually carries), confirmation links and the
 * deep-link query params chat replies and help pages use.
 */
import {
  AUDIT_CATEGORIES,
  AUDIT_OUTCOMES,
  AUDIT_RANGES,
  type AuditCategory,
  type AuditEvent,
  type AuditOutcomeFilter,
  type AuditRange,
} from "@/lib/settings-api/audit"
import { formatAuditActionLabel, formatAuditEntityLabel } from "@/lib/audit-summary"

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isUuid(value: unknown): value is string {
  return typeof value === "string" && UUID.test(value.trim())
}

export function eventTitle(log: AuditEvent): string {
  return formatAuditActionLabel(log.action)
}

export function eventActor(log: AuditEvent): string {
  const name = String(log.user_name ?? "").trim()
  if (name && !isUuid(name)) return name
  const email = String(log.user_email ?? "").trim()
  if (email) return email
  const agent = String(log.agent_name ?? "").trim()
  if (agent) return agent
  return "System"
}

export function eventEntity(log: AuditEvent): string {
  return formatAuditEntityLabel(log)
}

export function isErrorEvent(log: AuditEvent): boolean {
  return log.outcome === "error"
}

export interface MetaTile {
  k: string
  v: string
}

function scalar(value: unknown): string | null {
  if (value === null || value === undefined) return null
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : null
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return null
    return trimmed.length > 80 ? `${trimmed.slice(0, 79)}…` : trimmed
  }
  return null
}

function ms(value: unknown): string | null {
  const n = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN
  if (!Number.isFinite(n)) return null
  return n >= 10_000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n).toLocaleString()} ms`
}

/** [label, keys to try, formatter] in display order. */
const META_FIELDS: Array<[string, string[], ((value: unknown) => string | null)?]> = [
  ["Environment", ["environment", "env"]],
  ["Trigger", ["trigger", "trigger_type", "triggerType", "source_type"]],
  ["Records", ["records", "recordsProcessed", "records_processed", "record_count", "recordCount", "rows", "count"]],
  ["Duration", ["duration_ms", "durationMs", "latency_ms", "latencyMs", "preflight_duration_ms"], ms],
  ["Status", ["status", "outcome", "result"]],
  ["Vendor", ["vendor", "provider", "connector"]],
  ["Tool action", ["action"]],
  ["Run", ["run_id", "runId"]],
  ["Workflow", ["workflow_id", "workflowId"]],
  ["Agent", ["agent_id", "agentId", "operator_id"]],
  ["Task", ["task_id", "taskId"]],
  ["Plan", ["plan_id", "planId"]],
  ["Step", ["step_id", "stepId"]],
  ["Connector", ["connector_id", "connectorId"]],
  ["Source", ["source_id", "sourceId"]],
]

const SKIP_KEYS = new Set([
  "description",
  "message",
  "summary",
  "category",
  "error",
  "error_message",
  "errorMessage",
  "failure_reason",
  "failureReason",
])

function humanKey(key: string): string {
  const spaced = key.replace(/([a-z])([A-Z])/g, "$1 $2").replace(/[._-]+/g, " ").trim().toLowerCase()
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

/** Metadata tiles from the event's own keys (never invented). */
export function eventMeta(log: AuditEvent, max = 12): MetaTile[] {
  const details = (log.details ?? {}) as Record<string, unknown>
  const tiles: MetaTile[] = []
  const used = new Set<string>()
  for (const [label, keys, format] of META_FIELDS) {
    for (const key of keys) {
      if (!(key in details) || used.has(key)) continue
      const v = (format ?? scalar)(details[key])
      used.add(key)
      if (v) {
        tiles.push({ k: label, v })
        break
      }
    }
  }
  for (const [key, value] of Object.entries(details)) {
    if (tiles.length >= max) break
    if (used.has(key) || SKIP_KEYS.has(key)) continue
    const v = scalar(value)
    if (v) tiles.push({ k: humanKey(key), v })
  }
  if (log.entity_id && tiles.length < max) tiles.push({ k: "Record ID", v: log.entity_id })
  if (log.ip_address && tiles.length < max) tiles.push({ k: "IP address", v: String(log.ip_address) })
  return tiles.slice(0, max)
}

export function eventDescription(log: AuditEvent): string | null {
  const details = (log.details ?? {}) as Record<string, unknown>
  for (const key of ["description", "summary", "message"]) {
    const value = details[key]
    if (typeof value === "string" && value.trim()) return value.trim()
  }
  return null
}

export interface EventLink {
  label: string
  href: string
}

/** Links to the record an event wrote, so a write chat or an agent confirmed can be checked. */
export function eventLinks(log: AuditEvent): EventLink[] {
  const details = (log.details ?? {}) as Record<string, unknown>
  const links: EventLink[] = []
  const add = (label: string, href: string) => {
    if (!links.some((link) => link.href === href)) links.push({ label, href })
  }
  const pick = (...keys: string[]) => keys.map((key) => details[key]).find(isUuid)
  const entity = String(log.entity_type ?? "").toLowerCase()
  const entityId = isUuid(log.entity_id) ? log.entity_id : undefined

  const runId = pick("run_id", "runId") ?? (entity === "workflow_run" ? entityId : undefined)
  if (runId) add("Open run", `/runs/${runId}`)
  const workflowId = pick("workflow_id", "workflowId") ?? (entity === "workflow" ? entityId : undefined)
  if (workflowId) add("Open workflow", `/workflows/${workflowId}`)
  const agentId = pick("agent_id", "agentId", "operator_id") ?? (entity === "agent" || entity === "operator" ? entityId : undefined)
  if (agentId) add("Open agent", `/agents/${agentId}`)
  const connectorId = pick("connector_id", "connectorId") ?? (entity === "connector" ? entityId : undefined)
  if (connectorId) add("Open connector", `/connectors/${connectorId}`)
  const sourceId = pick("source_id", "sourceId") ?? (entity === "source" || entity === "rag_source" ? entityId : undefined)
  if (sourceId) add("Open source", `/sources/${sourceId}`)
  if (entity.startsWith("approval") || log.category === "approve") add("Open approvals", "/approvals")
  return links
}

export interface AuditDeepLink {
  range?: AuditRange
  category?: AuditCategory | "all"
  outcome?: AuditOutcomeFilter
  q?: string
  userId?: string
  action?: string
  entityType?: string
  view?: "tl" | "tb"
  open?: string
}

/**
 * Reads `/audit?range=30d&category=chat&outcome=err&q=hubspot&user=<id>&action=tool.invoke.completed&entity_type=workflow_run&event=<id>`.
 * Unknown values are ignored.
 */
export function parseAuditDeepLink(search: string): AuditDeepLink {
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search)
  const out: AuditDeepLink = {}
  const range = params.get("range")
  if (range && AUDIT_RANGES.some((option) => option.id === range)) out.range = range as AuditRange
  const category = params.get("category") ?? params.get("kind")
  if (category && (category === "all" || AUDIT_CATEGORIES.some((option) => option.id === category))) {
    out.category = category as AuditCategory | "all"
  }
  const outcome = params.get("outcome")
  if (outcome && AUDIT_OUTCOMES.some((option) => option.id === outcome)) out.outcome = outcome as AuditOutcomeFilter
  const q = params.get("q") ?? params.get("search")
  if (q?.trim()) out.q = q.trim().slice(0, 200)
  const user = params.get("user") ?? params.get("user_id")
  if (user?.trim()) out.userId = user.trim()
  const action = params.get("action")
  if (action?.trim()) out.action = action.trim()
  const entityType = params.get("entity_type") ?? params.get("entity")
  if (entityType?.trim()) out.entityType = entityType.trim()
  const view = params.get("view")
  if (view === "table" || view === "tb") out.view = "tb"
  if (view === "timeline" || view === "tl") out.view = "tl"
  const open = params.get("event")
  if (open?.trim()) out.open = open.trim()
  return out
}

export const AUDIT_PAGE_SIZE = 10

export function pageCountFor(total: number, size = AUDIT_PAGE_SIZE): number {
  return Math.max(1, Math.ceil(Math.max(0, total) / size))
}
