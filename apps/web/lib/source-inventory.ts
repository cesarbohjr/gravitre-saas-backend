export interface Source {
  id: string
  name: string
  type: string
  category: "sql" | "nosql" | "warehouse"
  status: "connected" | "disconnected" | "error" | "syncing" | "unknown"
  environment: "production" | "staging"
  lastSync: string
  lastSyncAt: number | null
  tables: number | null
  recordCount: number | null
  records: string
  description: string
  workflowsUsing: number | null
  operatorsUsing: number | null
  /** 0-100 when the backend reports it; null otherwise (never estimated client-side). */
  health: number | null
  topTables?: string[]
}

function optionalFiniteNumber(...candidates: unknown[]): number | null {
  for (const value of candidates) {
    if (value == null || value === "") continue
    const parsed = typeof value === "number" ? value : Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function inferCategory(type: string): Source["category"] {
  const normalized = type.toLowerCase()
  if (normalized.includes("postgres") || normalized.includes("mysql")) return "sql"
  if (normalized.includes("mongo")) return "nosql"
  return "warehouse"
}

function formatRelativeSync(iso: string | null | undefined): string {
  if (!iso) return "Never"
  const timestamp = new Date(iso)
  if (Number.isNaN(timestamp.getTime())) return "Never"
  const diffMs = Date.now() - timestamp.getTime()
  const minutes = Math.max(0, Math.floor(diffMs / 60000))
  if (minutes < 1) return "Just now"
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

export function formatCompactCount(value: number): string {
  if (!Number.isFinite(value) || value < 0) return "0"
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

export function formatReportedCount(value: number | null): string {
  return value == null ? "Not reported" : formatCompactCount(value)
}

export function normalizeSource(input: Record<string, unknown>): Source {
  const status = String(input.status ?? "unknown")
  const type = String(input.type ?? "Unknown")
  const rawRecordCount = optionalFiniteNumber(
    input.recordCount,
    input.record_count,
    input.recordsCount,
    input.records_count,
  )
  const stringRecords = typeof input.records === "string" ? input.records : ""
  const parsedStringRecords = Number.parseFloat(stringRecords.replace(/[^\d.]/g, ""))
  const recordsFromString = !stringRecords
    ? null
    : stringRecords.includes("M")
    ? parsedStringRecords * 1_000_000
    : stringRecords.includes("K")
    ? parsedStringRecords * 1_000
    : parsedStringRecords
  const effectiveRecordCount =
    rawRecordCount != null && rawRecordCount >= 0
      ? rawRecordCount
      : Number.isFinite(recordsFromString)
      ? recordsFromString
      : null
  const environment = String(input.environment ?? "production")
  const rawLastSync =
    (input.lastSync as string | null) ?? (input.last_sync as string | null) ?? (input.lastSyncAt as string | null)
  const lastSyncMs = rawLastSync ? new Date(rawLastSync).getTime() : Number.NaN
  return {
    id: String(input.id ?? ""),
    name: String(input.name ?? "source"),
    type,
    category:
      input.category === "sql" || input.category === "nosql" || input.category === "warehouse"
        ? input.category
        : inferCategory(type),
    status:
      status === "connected" || status === "disconnected" || status === "error" || status === "syncing"
        ? status
        : "unknown",
    environment: environment === "staging" ? "staging" : "production",
    lastSync: formatRelativeSync(rawLastSync),
    lastSyncAt: Number.isFinite(lastSyncMs) ? lastSyncMs : null,
    tables: optionalFiniteNumber(input.tables, input.tablesCount, input.tables_count),
    recordCount: effectiveRecordCount,
    records: formatReportedCount(effectiveRecordCount),
    description: String(input.description ?? `${type} data source`),
    workflowsUsing: optionalFiniteNumber(input.workflowsUsing, input.workflows_using),
    operatorsUsing: optionalFiniteNumber(input.operatorsUsing, input.operators_using),
    health:
      input.health != null && Number.isFinite(Number(input.health)) ? Number(input.health) : null,
    topTables: Array.isArray(input.topTables) ? (input.topTables as string[]) : [],
  }
}

export function normalizeSourcesResponse(payload: unknown): Source[] {
  if (!payload || typeof payload !== "object") return []
  const model = payload as Record<string, unknown>
  const raw = Array.isArray(model.sources) ? model.sources : null
  if (!raw) return []
  const normalized = raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => normalizeSource(item))
    .filter((item) => item.id.length > 0)
  return normalized
}

