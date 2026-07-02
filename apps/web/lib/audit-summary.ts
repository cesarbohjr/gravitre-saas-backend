import type { AuditLog } from "@/types/api"
import { categorizeAuditEvent } from "@/lib/audit-category"

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value)
}

function titleCase(value: string): string {
  return value
    .replace(/[._-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ")
}

function humanizeKey(key: string): string {
  return titleCase(key.replace(/([a-z])([A-Z])/g, "$1 $2"))
}

function humanizeValue(key: string, value: unknown): string {
  if (value == null || value === "") return ""
  if (typeof value === "boolean") return value ? "Yes" : "No"
  if (typeof value === "number") return String(value)
  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return ""
    if (isUuid(trimmed)) return "record"
    if (/^(auth_expired|pending_auth|connected|disconnected|failed|success)$/i.test(trimmed)) {
      return titleCase(trimmed.replace(/_/g, " "))
    }
    return trimmed
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "none"
    return value.map((item) => humanizeValue(key, item)).filter(Boolean).join(", ")
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>
    const preferred = ["message", "summary", "description", "reason", "outcome", "status"]
    for (const field of preferred) {
      const part = obj[field]
      if (typeof part === "string" && part.trim()) return part.trim()
    }
    return summarizeAuditDetails(obj).summary
  }
  return String(value)
}

const ACTION_LABELS: Record<string, string> = {
  "connector.auth.failed": "Connector sign-in failed",
  "connector.auth.expired": "Connector session expired",
  "connector.connected": "Connector connected",
  "connector.disconnected": "Connector disconnected",
  "connector.created": "Connector added",
  "connector.updated": "Connector updated",
  "connector.deleted": "Connector removed",
  "workflow.created": "Workflow created",
  "workflow.updated": "Workflow updated",
  "workflow.deleted": "Workflow deleted",
  "workflow.executed": "Workflow run started",
  "workflow.run.completed": "Workflow run completed",
  "workflow.run.failed": "Workflow run failed",
  "agent.created": "Agent created",
  "agent.updated": "Agent updated",
  "agent.started": "Agent activated",
  "agent.stopped": "Agent paused",
  "user.login": "User signed in",
  "user.logout": "User signed out",
  "approval.approved": "Approval granted",
  "approval.rejected": "Approval rejected",
  "approval.requested": "Approval requested",
  "billing.plan.changed": "Subscription plan changed",
  "settings.updated": "Settings updated",
}

export function formatAuditActionLabel(action: string | null | undefined): string {
  if (!action) return "System event"
  const normalized = action.trim().toLowerCase()
  if (ACTION_LABELS[normalized]) return ACTION_LABELS[normalized]
  if (ACTION_LABELS[action.trim()]) return ACTION_LABELS[action.trim()]
  return titleCase(action.replace(/\./g, " "))
}

export function formatAuditEntityLabel(log: AuditLog): string {
  if (log.entity_name?.trim()) return log.entity_name.trim()
  const entityType = log.entity_type ? titleCase(log.entity_type) : "Item"
  if (log.entity_id && !isUuid(log.entity_id)) return log.entity_id
  return entityType
}

export type AuditSummary = {
  summary: string
  outcome?: string
  bullets: string[]
  categoryLabel: string
}

export function summarizeAuditDetails(
  details: Record<string, unknown> | null | undefined,
  context?: { action?: string | null; entityType?: string | null },
): AuditSummary {
  const category = categorizeAuditEvent({
    action: context?.action,
    entityType: context?.entityType,
    category: typeof details?.category === "string" ? details.category : null,
  })

  if (!details || Object.keys(details).length === 0) {
    return {
      summary: "No additional details were recorded for this event.",
      bullets: [],
      categoryLabel: category.label,
    }
  }

  const description =
    typeof details.description === "string" && details.description.trim()
      ? details.description.trim()
      : typeof details.message === "string" && details.message.trim()
        ? details.message.trim()
        : null

  const bullets: string[] = []
  const skipKeys = new Set(["description", "message", "category"])

  for (const [key, value] of Object.entries(details)) {
    if (skipKeys.has(key)) continue
    const label = humanizeKey(key)
    const text = humanizeValue(key, value)
    if (!text || text === "record") continue
    bullets.push(`${label}: ${text}`)
  }

  const action = (context?.action ?? "").toLowerCase()

  if (action.includes("connector.auth.failed") || action.includes("connector.auth.expired")) {
    const vendor = humanizeValue("vendor", details.vendor)
    const authStatus = humanizeValue("authStatus", details.authStatus ?? details.auth_status)
    const environment = humanizeValue("environment", details.environment)
    const previous = humanizeValue("previousStatus", details.previousStatus ?? details.previous_status)
    const parts = [
      vendor ? `The ${vendor} connector` : "A connector",
      authStatus ? `could not stay signed in (${authStatus.toLowerCase()})` : "could not stay signed in",
    ]
    if (previous) parts.push(`after previously being ${previous.toLowerCase()}`)
    if (environment) parts.push(`in ${environment.toLowerCase()}`)
    return {
      summary: `${parts.join(" ")}. Reconnect the connector to restore access.`,
      outcome: authStatus || "Authentication issue",
      bullets,
      categoryLabel: category.label,
    }
  }

  if (action.includes("connector.connected")) {
    const vendor = humanizeValue("vendor", details.vendor)
    const environment = humanizeValue("environment", details.environment)
    return {
      summary: `${vendor ? `The ${vendor} connector` : "A connector"} connected successfully${
        environment ? ` in ${environment.toLowerCase()}` : ""
      }.`,
      outcome: "Connected",
      bullets,
      categoryLabel: category.label,
    }
  }

  if (description) {
    return {
      summary: description,
      bullets,
      categoryLabel: category.label,
    }
  }

  if (bullets.length === 1) {
    return { summary: bullets[0], bullets: [], categoryLabel: category.label }
  }

  if (bullets.length > 1) {
    return {
      summary: bullets.slice(0, 2).join(". ") + ".",
      bullets: bullets.slice(2),
      categoryLabel: category.label,
    }
  }

  return {
    summary: "System recorded this activity.",
    bullets: [],
    categoryLabel: category.label,
  }
}

export function summarizeAuditLog(log: AuditLog): AuditSummary {
  const fromDetails = summarizeAuditDetails(log.details ?? null, {
    action: log.action,
    entityType: log.entity_type,
  })
  const actor = log.user_name || log.user_email || "System"
  const actionLabel = formatAuditActionLabel(log.action)
  const entity = formatAuditEntityLabel(log)

  if (fromDetails.summary.startsWith("No additional details")) {
    return {
      ...fromDetails,
      summary: `${actor} ${actionLabel.toLowerCase()} for ${entity}.`,
    }
  }

  return fromDetails
}
