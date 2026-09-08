import type {
  DashboardLayout,
  DashboardWidget,
  KpiAvailability,
  KpiCategory,
  VizType,
  WidgetSize,
} from "./types"

export type KpiDefinition = {
  id: string
  category: KpiCategory
  name: string
  description: string
  availability: KpiAvailability
  /** Human-readable data source for the picker. */
  dataSource: string
  defaultViz: VizType
  allowedViz: VizType[]
  defaultSize: WidgetSize
  allowedSizes: WidgetSize[]
  href?: string
  recommended?: boolean
}

/**
 * Registry of KPIs grounded in real Gravitre APIs.
 * REQUIRES_TELEMETRY entries are omitted from the picker (not faked).
 */
export const KPI_REGISTRY: KpiDefinition[] = [
  // —— Agents ——
  {
    id: "agents.active",
    category: "agents",
    name: "Active agents",
    description: "Agents in active, processing, or running status",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "number",
    allowedViz: ["number", "number_trend", "status"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/agents",
    recommended: true,
  },
  {
    id: "agents.total",
    category: "agents",
    name: "Total agents",
    description: "All agents in the workspace",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "number",
    allowedViz: ["number"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/agents",
  },
  {
    id: "agents.idle",
    category: "agents",
    name: "Idle agents",
    description: "Agents currently idle",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "number",
    allowedViz: ["number", "status"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/agents",
  },
  {
    id: "agents.executing",
    category: "agents",
    name: "Executing agents",
    description: "Agents processing or running",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "number",
    allowedViz: ["number", "status"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/agents",
  },
  {
    id: "agents.error",
    category: "agents",
    name: "Failed agents",
    description: "Agents in error status",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "number",
    allowedViz: ["number", "status"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/agents",
  },
  {
    id: "agents.by_status",
    category: "agents",
    name: "Agents by status",
    description: "Donut breakdown of agent statuses",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "donut",
    allowedViz: ["donut", "bar"],
    defaultSize: "2x2",
    allowedSizes: ["2x2", "4x2"],
    href: "/agents",
    recommended: true,
  },
  {
    id: "agents.monitor",
    category: "agents",
    name: "Workflow monitor",
    description: "Agent / model / status / latency / last run table",
    availability: "available",
    dataSource: "agentsApi.list",
    defaultViz: "table",
    allowedViz: ["table"],
    defaultSize: "4x1",
    allowedSizes: ["4x1", "4x2"],
    href: "/agents",
    recommended: true,
  },

  // —— Workflows ——
  {
    id: "workflows.active",
    category: "workflows",
    name: "Active workflows",
    description: "Workflows with status active",
    availability: "available",
    dataSource: "metricsApi.overview · activeWorkflows",
    defaultViz: "number",
    allowedViz: ["number", "number_trend"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/workflows",
    recommended: true,
  },
  {
    id: "workflows.total",
    category: "workflows",
    name: "Total workflows",
    description: "All workflows in the workspace",
    availability: "available",
    dataSource: "metricsApi.overview · totalWorkflows",
    defaultViz: "number",
    allowedViz: ["number"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/workflows",
  },

  // —— Runs ——
  {
    id: "runs.success_rate",
    category: "runs",
    name: "Task success rate",
    description: "Completed / (completed + failed) from live runs",
    availability: "available",
    dataSource: "metricsApi.overview · successRate",
    defaultViz: "number",
    allowedViz: ["number", "number_trend", "progress", "sparkline"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1", "2x2"],
    href: "/runs",
    recommended: true,
  },
  {
    id: "runs.avg_duration",
    category: "runs",
    name: "Average execution time",
    description: "Mean run duration in the selected range",
    availability: "available",
    dataSource: "metricsApi.overview · avgDuration",
    defaultViz: "number",
    allowedViz: ["number", "number_trend", "sparkline"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/runs",
    recommended: true,
  },
  {
    id: "runs.total",
    category: "runs",
    name: "Total runs",
    description: "Run count in the selected range",
    availability: "available",
    dataSource: "metricsApi.overview · totalRuns",
    defaultViz: "number",
    allowedViz: ["number", "number_trend", "sparkline"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/runs",
  },
  {
    id: "runs.avg_latency",
    category: "runs",
    name: "Average latency",
    description: "Average latency from metrics overview",
    availability: "available",
    dataSource: "metricsApi.overview · avgLatency",
    defaultViz: "number",
    allowedViz: ["number", "sparkline"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/metrics",
  },
  {
    id: "runs.breakdown",
    category: "runs",
    name: "Tasks / runs breakdown",
    description: "Stacked or horizontal run volume by day",
    availability: "available",
    dataSource: "metricsApi.overview · trends.totalRuns",
    defaultViz: "stacked_bar",
    allowedViz: ["stacked_bar", "bar", "line"],
    defaultSize: "2x2",
    allowedSizes: ["2x2", "4x2"],
    href: "/runs",
    recommended: true,
  },

  // —— Approvals ——
  {
    id: "approvals.pending",
    category: "approvals",
    name: "Pending approvals",
    description: "Approvals awaiting decision",
    availability: "available",
    dataSource: "approvalsApi.list",
    defaultViz: "number",
    allowedViz: ["number", "status", "list"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1", "2x2"],
    href: "/approvals",
    recommended: true,
  },

  // —— Connectors ——
  {
    id: "connectors.active",
    category: "connectors",
    name: "Active connectors",
    description: "Healthy / connected connectors",
    availability: "available",
    dataSource: "metricsApi.overview · activeConnectors",
    defaultViz: "number",
    allowedViz: ["number", "health"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/connectors",
  },
  {
    id: "connectors.total",
    category: "connectors",
    name: "Total connectors",
    description: "All connectors in the workspace",
    availability: "available",
    dataSource: "metricsApi.overview · totalConnectors",
    defaultViz: "number",
    allowedViz: ["number"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/connectors",
  },
  {
    id: "connectors.health_latency",
    category: "connectors",
    name: "Connector health latency",
    description: "Average OAuth health-check latency",
    availability: "available",
    dataSource: "metricsApi.overview · connectorHealthLatencyMs",
    defaultViz: "number",
    allowedViz: ["number", "health"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/connectors",
  },

  // —— GIBE ——
  {
    id: "gibe.avg_confidence",
    category: "gibe",
    name: "Average confidence",
    description: "Trust summary average confidence (7d)",
    availability: "available",
    dataSource: "intelligenceApi.trustSummary",
    defaultViz: "number",
    allowedViz: ["number", "progress"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/intelligence",
  },
  {
    id: "gibe.learning_query",
    category: "gibe",
    name: "Learning · query progress",
    description: "Query rows toward learning target",
    availability: "available",
    dataSource: "intelligenceApi.learningProgress",
    defaultViz: "progress",
    allowedViz: ["progress", "number"],
    defaultSize: "2x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/learning",
  },
  {
    id: "gibe.learning_workflow",
    category: "gibe",
    name: "Learning · workflow progress",
    description: "Workflow rows toward observed target",
    availability: "available",
    dataSource: "intelligenceApi.learningProgress",
    defaultViz: "progress",
    allowedViz: ["progress", "number"],
    defaultSize: "2x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/learning",
  },
  {
    id: "gibe.revenue_risks",
    category: "gibe",
    name: "Revenue risk radar",
    description: "Business impact revenue risk items",
    availability: "available",
    dataSource: "intelligenceApi.businessImpact",
    defaultViz: "list",
    allowedViz: ["list"],
    defaultSize: "2x2",
    allowedSizes: ["2x2", "4x2"],
    href: "/intelligence",
  },
  {
    id: "gibe.predictive",
    category: "gibe",
    name: "Predictive operations",
    description: "Predictive ops summary when available",
    availability: "available",
    dataSource: "architectureAdminApi.predictiveOps",
    defaultViz: "status",
    allowedViz: ["status", "list"],
    defaultSize: "2x2",
    allowedSizes: ["2x1", "2x2"],
    href: "/intelligence",
  },

  // —— Memory / system (real ai-os fields) ——
  {
    id: "system.ml_models_live",
    category: "system",
    name: "ML models live",
    description: "Live ML models from AI OS status",
    availability: "available",
    dataSource: "architectureAdminApi.aiOsStatus · ml_models_live",
    defaultViz: "number",
    allowedViz: ["number", "health"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/intelligence",
  },
  {
    id: "system.memory_promotions",
    category: "memory",
    name: "Memory promotions pending",
    description: "Pending memory promotions",
    availability: "available",
    dataSource: "architectureAdminApi.aiOsStatus · memory_promotions_pending",
    defaultViz: "number",
    allowedViz: ["number", "status"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/intelligence",
  },
  {
    id: "system.architecture_live",
    category: "system",
    name: "Architecture systems live",
    description: "Count of live architecture systems",
    availability: "available",
    dataSource: "architectureAdminApi.aiOsStatus · architecture_systems_live",
    defaultViz: "number",
    allowedViz: ["number", "health"],
    defaultSize: "1x1",
    allowedSizes: ["1x1"],
    href: "/intelligence",
  },

  // —— Usage ——
  {
    id: "usage.records_processed",
    category: "usage",
    name: "Records processed",
    description: "Records processed in the selected range",
    availability: "available",
    dataSource: "metricsApi.overview · recordsProcessed",
    defaultViz: "number",
    allowedViz: ["number", "sparkline"],
    defaultSize: "1x1",
    allowedSizes: ["1x1", "2x1"],
    href: "/metrics",
  },
]

export const KPI_BY_ID = Object.fromEntries(KPI_REGISTRY.map((k) => [k.id, k])) as Record<
  string,
  KpiDefinition
>

export const KPI_CATEGORIES: { id: KpiCategory; label: string }[] = [
  { id: "agents", label: "Agents" },
  { id: "workflows", label: "Workflows" },
  { id: "runs", label: "Runs" },
  { id: "approvals", label: "Approvals" },
  { id: "connectors", label: "Connectors" },
  { id: "models", label: "AI / Models" },
  { id: "gibe", label: "GIBE / Intelligence" },
  { id: "memory", label: "Memory / RAG" },
  { id: "voice", label: "Voice" },
  { id: "governance", label: "Governance" },
  { id: "usage", label: "Usage" },
  { id: "system", label: "System Health" },
]

export function pickableKpis(): KpiDefinition[] {
  return KPI_REGISTRY.filter((k) => k.availability === "available" || k.availability === "derivable")
}

function widget(
  metricId: string,
  order: number,
  overrides?: Partial<DashboardWidget>,
): DashboardWidget {
  const def = KPI_BY_ID[metricId]
  return {
    id: `w_${metricId.replace(/\./g, "_")}`,
    metricId,
    size: def?.defaultSize ?? "1x1",
    order,
    visualization: def?.defaultViz ?? "number",
    ...overrides,
  }
}

/** Nodus-faithful default: 4 KPIs → monitor → donut + stacked bars. */
export function createDefaultLayout(): DashboardLayout {
  return {
    version: 1,
    globalRange: "7d",
    updatedAt: new Date().toISOString(),
    widgets: [
      widget("agents.active", 0),
      widget("runs.success_rate", 1),
      widget("runs.avg_duration", 2),
      widget("workflows.active", 3),
      widget("agents.monitor", 4, { size: "4x1" }),
      widget("agents.by_status", 5, { size: "2x2" }),
      widget("runs.breakdown", 6, { size: "2x2" }),
    ],
  }
}

export type DashboardPresetId =
  | "operations"
  | "executive"
  | "agents"
  | "workflows"
  | "models"
  | "gibe"
  | "governance"
  | "system"

export type DashboardPreset = {
  id: DashboardPresetId
  name: string
  description: string
  build: () => DashboardLayout
}

function layoutFromMetricIds(
  metricIds: string[],
  globalRange: DashboardLayout["globalRange"] = "7d",
): DashboardLayout {
  return {
    version: 1,
    globalRange,
    updatedAt: new Date().toISOString(),
    widgets: metricIds.map((metricId, order) => widget(metricId, order)),
  }
}

/** Saved collections of existing registry widgets — no invented metrics. */
export const DASHBOARD_PRESETS: DashboardPreset[] = [
  {
    id: "operations",
    name: "Operations",
    description: "Nodus default — agents, success, latency, workflows, monitor, breakdowns",
    build: createDefaultLayout,
  },
  {
    id: "executive",
    name: "Executive",
    description: "Success rate, workflows, approvals, confidence, revenue risks",
    build: () =>
      layoutFromMetricIds([
        "runs.success_rate",
        "workflows.active",
        "approvals.pending",
        "gibe.avg_confidence",
        "runs.total",
        "connectors.active",
        "gibe.revenue_risks",
        "gibe.predictive",
      ]),
  },
  {
    id: "agents",
    name: "Agents",
    description: "Agent roster health and monitor table",
    build: () =>
      layoutFromMetricIds([
        "agents.active",
        "agents.total",
        "agents.executing",
        "agents.error",
        "agents.monitor",
        "agents.by_status",
      ]),
  },
  {
    id: "workflows",
    name: "Workflows",
    description: "Workflow and run throughput focus",
    build: () =>
      layoutFromMetricIds([
        "workflows.active",
        "workflows.total",
        "runs.success_rate",
        "runs.avg_duration",
        "runs.total",
        "runs.breakdown",
        "approvals.pending",
      ]),
  },
  {
    id: "models",
    name: "AI / Models",
    description: "Model and architecture live counts with run latency",
    build: () =>
      layoutFromMetricIds([
        "system.ml_models_live",
        "system.architecture_live",
        "runs.avg_latency",
        "runs.success_rate",
        "usage.records_processed",
        "runs.breakdown",
      ]),
  },
  {
    id: "gibe",
    name: "GIBE",
    description: "Confidence, learning progress, risks, predictive ops",
    build: () =>
      layoutFromMetricIds([
        "gibe.avg_confidence",
        "gibe.learning_query",
        "gibe.learning_workflow",
        "system.memory_promotions",
        "gibe.revenue_risks",
        "gibe.predictive",
      ]),
  },
  {
    id: "governance",
    name: "Governance",
    description: "Approvals and connector health",
    build: () =>
      layoutFromMetricIds([
        "approvals.pending",
        "connectors.active",
        "connectors.health_latency",
        "runs.success_rate",
        "agents.error",
        "agents.monitor",
      ]),
  },
  {
    id: "system",
    name: "System Health",
    description: "Architecture, connectors, latency, and promotions",
    build: () =>
      layoutFromMetricIds([
        "system.architecture_live",
        "system.ml_models_live",
        "connectors.active",
        "connectors.health_latency",
        "runs.avg_latency",
        "system.memory_promotions",
        "runs.breakdown",
      ]),
  },
]

export function getDashboardPreset(id: string): DashboardPreset | undefined {
  return DASHBOARD_PRESETS.find((p) => p.id === id)
}
