/**
 * The plain-language "which sources did this answer use" record the assistant
 * stream sends on LIVE answers (`data-intelligence` → `contextSources`).
 * Built server-side in backend/app/services/context_sources_summary.py.
 */

export type ContextSourceUsed = {
  name: string
  kind: string
  /** e.g. "updated 2 hours ago" — only present when a real date was recorded. */
  freshness?: string
}

export type ContextSourceSkipped = {
  reason: string
  label: string
  count: number
}

export type ContextSourcesSummary = {
  summary: string
  used: ContextSourceUsed[]
  usedCount?: number
  skipped: ContextSourceSkipped[]
  freshnessChecked?: boolean
}

export const CONTEXT_HELP_HREF = "/ai/help/context"

/** Settings › AI models › Customer data (the customer-context opt-in). */
export const CUSTOMER_DATA_SETTINGS_HREF = "/settings?section=ai-models#customer-data"

function str(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

/** Accepts the raw stream value; returns null for anything that is not a usable record. */
export function parseContextSources(value: unknown): ContextSourcesSummary | null {
  if (!value || typeof value !== "object") return null
  const row = value as Record<string, unknown>
  const summary = str(row.summary)
  const used: ContextSourceUsed[] = Array.isArray(row.used)
    ? row.used.flatMap((item) => {
        if (!item || typeof item !== "object") return []
        const rec = item as Record<string, unknown>
        const name = str(rec.name)
        if (!name) return []
        const freshness = str(rec.freshness)
        return [{ name, kind: str(rec.kind) || "Source", ...(freshness ? { freshness } : {}) }]
      })
    : []
  const skipped: ContextSourceSkipped[] = Array.isArray(row.skipped)
    ? row.skipped.flatMap((item) => {
        if (!item || typeof item !== "object") return []
        const rec = item as Record<string, unknown>
        const count = Number(rec.count)
        const label = str(rec.label)
        if (!label || !Number.isFinite(count) || count <= 0) return []
        return [{ reason: str(rec.reason), label, count }]
      })
    : []
  if (!summary && used.length === 0 && skipped.length === 0) return null
  return {
    summary,
    used,
    usedCount: typeof row.usedCount === "number" ? row.usedCount : undefined,
    skipped,
    freshnessChecked: row.freshnessChecked === true,
  }
}
