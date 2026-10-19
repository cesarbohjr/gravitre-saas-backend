/**
 * Audit trail data (GET /api/audit, /api/audit/summary, /api/audit/export).
 * Filters, search and pagination run on the server, and the list returns
 * totals (events, distinct actors, errors) for the whole filtered result.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"
import type { AuditLog, AuditSummary } from "@/types/api"

export type AuditRange = "24h" | "7d" | "30d"
export type AuditCategory = "sync" | "run" | "approve" | "agent" | "member" | "setting" | "chat"
export type AuditOutcomeFilter = "all" | "ok" | "err"

export const AUDIT_RANGES: Array<{ id: AuditRange; label: string }> = [
  { id: "7d", label: "Last 7 days" },
  { id: "30d", label: "Last 30 days" },
  { id: "24h", label: "Last 24 hours" },
]

/** Design's Action filter, mapped server side to real action prefixes (backend/app/routers/audit.py). */
export const AUDIT_CATEGORIES: Array<{ id: AuditCategory; label: string }> = [
  { id: "sync", label: "Source syncs" },
  { id: "run", label: "Workflow runs" },
  { id: "approve", label: "Approvals" },
  { id: "agent", label: "Agent changes" },
  { id: "member", label: "Members" },
  { id: "setting", label: "Settings" },
  { id: "chat", label: "Chat writes" },
]

export const AUDIT_OUTCOMES: Array<{ id: AuditOutcomeFilter; label: string }> = [
  { id: "all", label: "All outcomes" },
  { id: "ok", label: "Succeeded" },
  { id: "err", label: "Errors" },
]

export interface AuditEvent extends AuditLog {
  category?: AuditCategory | null
  outcome?: "success" | "error"
  error_message?: string | null
}

export interface AuditListPayload {
  logs: AuditEvent[]
  total: number
  hasMore: boolean
  actors?: number
  errors?: number
  truncated?: boolean
  scanLimit?: number
}

export interface AuditSummaryPayload extends AuditSummary {
  byCategory?: Partial<Record<AuditCategory, number>>
}

export interface AuditQuery {
  range: AuditRange
  category?: AuditCategory | "all"
  outcome?: AuditOutcomeFilter
  q?: string
  userId?: string
  action?: string
  entityType?: string
}

export function rangeStart(range: AuditRange, now = Date.now()): string {
  const hours = range === "24h" ? 24 : range === "30d" ? 30 * 24 : 7 * 24
  return new Date(now - hours * 60 * 60 * 1000).toISOString()
}

/** Query string shared by the list and the export, so exports match the filters on screen. */
export function auditParams(query: AuditQuery, from: string): URLSearchParams {
  const params = new URLSearchParams()
  params.set("from", from)
  if (query.category && query.category !== "all") params.set("category", query.category)
  if (query.outcome && query.outcome !== "all") params.set("outcome", query.outcome)
  const q = query.q?.trim()
  if (q) params.set("q", q)
  if (query.userId) params.set("user_id", query.userId)
  if (query.action) params.set("action", query.action)
  if (query.entityType) params.set("entity_type", query.entityType)
  return params
}

export function listAudit(query: AuditQuery, from: string, page: { limit: number; offset: number }) {
  const params = auditParams(query, from)
  params.set("limit", String(page.limit))
  params.set("offset", String(page.offset))
  return fetcher<AuditListPayload>(`/api/audit?${params.toString()}`)
}

export function auditSummary(range: AuditRange) {
  return fetcher<AuditSummaryPayload>(`/api/audit/summary?range=${range}`)
}

/** Whole date range with the current filters, not just the visible page. */
export function exportAudit(format: "csv" | "json", query: AuditQuery, from: string) {
  const params = auditParams(query, from)
  params.set("format", format)
  return apiFetch(`/api/audit/export?${params.toString()}`)
}
