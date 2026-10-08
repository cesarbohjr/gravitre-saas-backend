/**
 * Signals read from a real agent job (status, error, result.tool_calls) for
 * the Assignments board and detail page. Nothing here invents a value: every
 * function returns null when the job did not report the underlying data.
 */
import type { AgentJob } from "@/hooks/use-async-job"

export type AssignmentFlagTone = "amber" | "red" | "brand" | "neutral"

export interface AssignmentFlag {
  label: string
  tone: AssignmentFlagTone
  /** True when the operator should look at the outcome (failure, block, partial run). */
  needsLook: boolean
}

export interface ActionResult {
  key: string
  /** Plain-language name, e.g. "Search organizations". */
  label: string
  /** The tool or action id as the runtime reported it, shown in mono. */
  tool: string
  ok: boolean
  error: string | null
}

export interface ActionStats {
  total: number
  failed: number
  succeeded: number
}

type ToolCallRow = {
  tool?: unknown
  action?: unknown
  result?: { success?: unknown; error?: unknown; error_detail?: unknown; action?: unknown } | null
}

const VERBS = new Set([
  "list",
  "search",
  "get",
  "create",
  "update",
  "delete",
  "add",
  "remove",
  "send",
  "find",
  "enrich",
  "fetch",
  "sync",
  "read",
  "write",
  "post",
  "upsert",
  "lookup",
  "query",
  "export",
  "import",
  "match",
])

function capitalize(text: string): string {
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : text
}

/** "apollo.organizations.search" → "Search organizations"; "apollo.lists.list" → "List Apollo lists". */
export function humanizeToolName(id: string): string {
  const parts = id
    .trim()
    .split(/[._:/\s-]+/)
    .map((part) => part.toLowerCase())
    .filter(Boolean)
  if (parts.length === 0) return "Tool call"
  if (parts.length === 1) return capitalize(parts[0])
  const [provider, ...rest] = parts
  const last = rest[rest.length - 1]
  if (rest.length >= 2 && VERBS.has(last)) {
    const noun = rest.slice(0, -1).join(" ")
    const nounRoot = noun.replace(/s$/, "")
    if (nounRoot === last) return `${capitalize(last)} ${capitalize(provider)} ${noun}`
    return `${capitalize(last)} ${noun}`
  }
  if (VERBS.has(rest[0])) return capitalize(rest.join(" "))
  return capitalize(rest.join(" "))
}

function asText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim()
  return null
}

/** Each reported tool call as a result row. Empty when the job reported none. */
export function actionResults(toolCalls: unknown): ActionResult[] {
  if (!Array.isArray(toolCalls)) return []
  const rows: ActionResult[] = []
  toolCalls.forEach((entry, index) => {
    if (!entry || typeof entry !== "object") return
    const row = entry as ToolCallRow
    const result = row.result && typeof row.result === "object" ? row.result : null
    const tool = asText(result?.action) || asText(row.action) || asText(row.tool) || "tool"
    const ok = result?.success === true
    rows.push({
      key: `${index}-${tool}`,
      label: humanizeToolName(tool),
      tool,
      ok,
      error: ok ? null : asText(result?.error) || asText(result?.error_detail),
    })
  })
  return rows
}

export function actionStats(toolCalls: unknown): ActionStats | null {
  const rows = actionResults(toolCalls)
  if (rows.length === 0) return null
  const failed = rows.filter((row) => !row.ok).length
  return { total: rows.length, failed, succeeded: rows.length - failed }
}

/** Agent-reported confidence as a whole percent; null when not reported or invalid. */
export function reportedConfidencePercent(raw: unknown): number | null {
  if (typeof raw !== "number" || !Number.isFinite(raw) || raw < 0 || raw > 100) return null
  return Math.round(raw <= 1 ? raw * 100 : raw)
}

/** Short label for why work stopped, read from the error text. */
export function classifyIssue(text: string): string {
  const value = text.toLowerCase()
  if (
    /upgrade|subscription|quota|billing|payment required|\b402\b|out of credits|plan (limit|with|does not|doesn't)|(paid|your|current|free|pro|starter|basic|enterprise) plan|requires? an? [\w.]+ plan/.test(value)
  ) {
    return "Blocked by plan limit"
  }
  if (/rate.?limit|too many requests|\b429\b/.test(value)) return "Rate limited"
  if (/not connected|tool_not_available|not permitted|no connector|connect (the|an|your) /.test(value)) {
    return "App not connected"
  }
  if (/unauthori[sz]ed|forbidden|permission|\b401\b|\b403\b|credential|expired|re-?authori|reconnect|access denied|api key/.test(value)) {
    return "Needs access"
  }
  if (/timed? ?out|timeout/.test(value)) return "Timed out"
  return "Failed"
}

function firstFailure(toolCalls: unknown): string | null {
  return actionResults(toolCalls).find((row) => !row.ok && row.error)?.error ?? null
}

/** The problem text the job reported: job error, result error, then the first failed tool call. */
export function reportedIssueText(job: Pick<AgentJob, "status" | "error" | "result">): string | null {
  const result = (job.result ?? null) as Record<string, unknown> | null
  return (
    asText(job.error) ||
    asText(result?.error) ||
    firstFailure(result?.tool_calls) ||
    null
  )
}

/** The status flag shown on a card and the detail header, derived only from job data. */
export function assignmentFlag(job: Pick<AgentJob, "status" | "error" | "result">): AssignmentFlag | null {
  const result = (job.result ?? null) as Record<string, unknown> | null
  if (job.status === "cancelled") return { label: "Cancelled", tone: "neutral", needsLook: false }
  if (job.status === "failed") {
    const text = reportedIssueText(job)
    return { label: text ? classifyIssue(text) : "Failed", tone: "amber", needsLook: true }
  }
  if (job.status !== "completed") return null
  if (result?.approval_status === "rejected") return { label: "Rejected", tone: "red", needsLook: false }
  const stats = actionStats(result?.tool_calls)
  const resultError = asText(result?.error)
  if (resultError || (stats && stats.failed > 0)) {
    const text = resultError || firstFailure(result?.tool_calls)
    const label = text ? classifyIssue(text) : "Some actions failed"
    return { label: label === "Failed" ? "Some actions failed" : label, tone: "amber", needsLook: true }
  }
  if (result?.approval_status === "approved") return { label: "Approved", tone: "brand", needsLook: false }
  return null
}

const DOMAIN = /\b((?:https?:\/\/)?(?:[a-z0-9-]+\.)+(?:io|com|ai|app|co|net|org|dev)(?:\/[^\s)"'<>]*)?)/i

/**
 * An external upgrade link, only when the reported text names one and talks
 * about a plan or upgrade. Returns null otherwise.
 */
export function upgradeLinkFrom(text: string | null | undefined): { href: string; label: string } | null {
  if (!text) return null
  if (!/\b(upgrade|plan|subscription|billing)\b/i.test(text)) return null
  const match = text.match(DOMAIN)
  if (!match) return null
  const raw = match[1].replace(/[.,;:]+$/, "")
  const href = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`
  let host: string
  try {
    host = new URL(href).hostname
  } catch {
    return null
  }
  const labels = host.split(".").filter(Boolean)
  const name = labels.length >= 2 ? labels[labels.length - 2] : labels[0]
  if (!name) return null
  return { href, label: `Upgrade ${capitalize(name)} plan` }
}

/** "Aug 1" style date for cards; empty when the timestamp is missing or unparseable. */
export function shortDate(iso: string | null | undefined, withYear = false): string {
  if (!iso) return ""
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return ""
  return parsed.toLocaleDateString(undefined, withYear ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", day: "numeric" })
}
