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
  /** Catalog type id ("hubspot", "csv_upload"); falls back to `type`. */
  typeId: string
  /** Last sync failure message stored on the source, when there is one. */
  lastSyncError: string | null
  /** Connector this source reads through (OAuth vendors), when linked. */
  connectorId?: string
  /** Up to 7 most recent sync outcomes from the audit trail, oldest first. */
  recentSyncs: SourceSyncPoint[]
}

export interface SourceSyncPoint {
  status: "ok" | "fail"
  records: number | null
  error: string | null
  createdAt: string | null
}

export interface SourceIngestionEvent {
  sourceId: string
  kind: "sync" | "created" | "updated"
  status: "ok" | "fail" | null
  records: number | null
  error: string | null
  createdAt: string | null
}

function syncStatus(value: unknown): "ok" | "fail" | null {
  const raw = String(value ?? "").toLowerCase()
  if (!raw) return null
  if (["failed", "error", "fail", "failure"].includes(raw)) return "fail"
  return "ok"
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null
}

function normalizeSyncPoint(item: Record<string, unknown>): SourceSyncPoint {
  return {
    status: syncStatus(item.status) ?? "ok",
    records: optionalFiniteNumber(item.records),
    error: optionalString(item.error),
    createdAt: optionalString(item.createdAt),
  }
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
    typeId: String(input.typeId ?? input.type ?? "").toLowerCase(),
    lastSyncError: optionalString(input.lastSyncError),
    connectorId: optionalString(input.connectorId) ?? undefined,
    recentSyncs: Array.isArray(input.recentSyncs)
      ? (input.recentSyncs as unknown[])
          .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
          .map(normalizeSyncPoint)
          .slice(-7)
      : [],
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


/** The "Recent ingestion" feed the sources list returns beside the inventory. */
export function normalizeIngestionFeed(payload: unknown): SourceIngestionEvent[] {
  if (!payload || typeof payload !== "object") return []
  const raw = (payload as Record<string, unknown>).ingestion
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => {
      const kind = String(item.kind ?? "sync")
      return {
        sourceId: String(item.sourceId ?? ""),
        kind: kind === "created" || kind === "updated" ? kind : "sync",
        status: syncStatus(item.status),
        records: optionalFiniteNumber(item.records),
        error: optionalString(item.error),
        createdAt: optionalString(item.createdAt),
      } satisfies SourceIngestionEvent
    })
    .filter((item) => item.sourceId.length > 0)
}

export { formatRelativeSync }
