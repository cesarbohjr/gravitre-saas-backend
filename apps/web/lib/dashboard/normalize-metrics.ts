/**
 * Normalize metrics overview payloads — live API is camelCase;
 * older clients / docs used snake_case. Prefer camel; fall back to snake.
 */

export type NormalizedMetricsOverview = {
  totalWorkflows: number | null
  activeWorkflows: number | null
  totalRuns: number | null
  successRate: number | null
  avgDuration: number | null
  avgLatency: number | null
  recordsProcessed: number | null
  activeConnectors: number | null
  totalConnectors: number | null
  connectorHealthLatencyMs: number | null
  connectorHealthLatencyP95Ms: number | null
  changes: {
    totalRuns: number | null
    successRate: number | null
    recordsProcessed: number | null
    avgLatency: number | null
  }
  trends: {
    totalRuns: number[]
    successRate: number[]
    recordsProcessed: number[]
    avgLatency: number[]
  }
}

function num(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number.parseFloat(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function numArray(value: unknown): number[] {
  if (!Array.isArray(value)) return []
  return value.map((v) => num(v) ?? 0)
}

export function normalizeMetricsOverview(payload: unknown): NormalizedMetricsOverview {
  const empty: NormalizedMetricsOverview = {
    totalWorkflows: null,
    activeWorkflows: null,
    totalRuns: null,
    successRate: null,
    avgDuration: null,
    avgLatency: null,
    recordsProcessed: null,
    activeConnectors: null,
    totalConnectors: null,
    connectorHealthLatencyMs: null,
    connectorHealthLatencyP95Ms: null,
    changes: {
      totalRuns: null,
      successRate: null,
      recordsProcessed: null,
      avgLatency: null,
    },
    trends: {
      totalRuns: [],
      successRate: [],
      recordsProcessed: [],
      avgLatency: [],
    },
  }
  if (!payload || typeof payload !== "object") return empty
  const m = payload as Record<string, unknown>
  const changes = (m.changes as Record<string, unknown> | undefined) ?? {}
  const trends = (m.trends as Record<string, unknown> | undefined) ?? {}

  return {
    totalWorkflows: num(m.totalWorkflows ?? m.total_workflows),
    activeWorkflows: num(m.activeWorkflows ?? m.active_workflows),
    totalRuns: num(m.totalRuns ?? m.total_runs),
    successRate: num(m.successRate ?? m.success_rate),
    avgDuration: num(m.avgDuration ?? m.avg_run_duration_ms ?? m.avg_duration),
    avgLatency: num(m.avgLatency ?? m.avg_latency),
    recordsProcessed: num(m.recordsProcessed ?? m.records_processed),
    activeConnectors: num(m.activeConnectors ?? m.active_connectors),
    totalConnectors: num(m.totalConnectors ?? m.total_connectors),
    connectorHealthLatencyMs: num(
      m.connectorHealthLatencyMs ?? m.connector_health_latency_ms,
    ),
    connectorHealthLatencyP95Ms: num(
      m.connectorHealthLatencyP95Ms ?? m.connector_health_latency_p95_ms,
    ),
    changes: {
      totalRuns: num(changes.totalRuns),
      successRate: num(changes.successRate),
      recordsProcessed: num(changes.recordsProcessed),
      avgLatency: num(changes.avgLatency),
    },
    trends: {
      totalRuns: numArray(trends.totalRuns),
      successRate: numArray(trends.successRate),
      recordsProcessed: numArray(trends.recordsProcessed),
      avgLatency: numArray(trends.avgLatency),
    },
  }
}

/** Map AI OS status to honest field names (backend ≠ legacy home snake keys). */
export type NormalizedAiOs = {
  mlModelsLive: number | null
  mlModelsPlanned: number | null
  memoryPromotionsPending: number | null
  architectureSystemsLive: number | null
  architectureSystemsPlanned: number | null
  lastIntelligenceRun: string | null
}

export function normalizeAiOsStatus(payload: unknown): NormalizedAiOs {
  const empty: NormalizedAiOs = {
    mlModelsLive: null,
    mlModelsPlanned: null,
    memoryPromotionsPending: null,
    architectureSystemsLive: null,
    architectureSystemsPlanned: null,
    lastIntelligenceRun: null,
  }
  if (!payload || typeof payload !== "object") return empty
  const m = payload as Record<string, unknown>
  const engine =
    m.intelligence_engine && typeof m.intelligence_engine === "object"
      ? (m.intelligence_engine as Record<string, unknown>)
      : {}

  return {
    mlModelsLive: num(m.ml_models_live ?? m.mlModelsLive ?? m.ml_models_active),
    mlModelsPlanned: num(m.ml_models_planned ?? m.mlModelsPlanned),
    memoryPromotionsPending: num(
      m.memory_promotions_pending ?? m.memoryPromotionsPending ?? m.memories_count,
    ),
    architectureSystemsLive: num(
      m.architecture_systems_live ?? m.architectureSystemsLive ?? m.systems_online,
    ),
    architectureSystemsPlanned: num(
      m.architecture_systems_planned ?? m.architectureSystemsPlanned,
    ),
    lastIntelligenceRun:
      typeof engine.last_run === "string"
        ? engine.last_run
        : typeof m.last_learning_cycle === "string"
          ? m.last_learning_cycle
          : typeof m.last_cycle_at === "string"
            ? m.last_cycle_at
            : null,
  }
}
