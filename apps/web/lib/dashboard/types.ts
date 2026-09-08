/** Configurable home dashboard widget model (Nodus-faithful grid). */

export type DashboardRange = "1h" | "24h" | "7d" | "30d" | "90d"

export type VizType =
  | "number"
  | "number_trend"
  | "progress"
  | "sparkline"
  | "donut"
  | "bar"
  | "line"
  | "stacked_bar"
  | "table"
  | "status"
  | "list"
  | "timeline"
  | "health"

/** Grid size presets on a 12-column board. */
export type WidgetSize = "1x1" | "2x1" | "2x2" | "4x1" | "4x2"

export type KpiCategory =
  | "agents"
  | "workflows"
  | "runs"
  | "approvals"
  | "connectors"
  | "models"
  | "gibe"
  | "memory"
  | "voice"
  | "governance"
  | "usage"
  | "system"

export type KpiAvailability = "available" | "derivable" | "requires_telemetry"

export type DashboardWidget = {
  id: string
  metricId: string
  title?: string
  size: WidgetSize
  /** Order index — packed left-to-right, top-to-bottom with auto reflow. */
  order: number
  visualization: VizType
  filters?: {
    range?: DashboardRange
    agentId?: string
    workflowId?: string
    connectorId?: string
    status?: string
  }
  refreshSec?: number
  config?: Record<string, unknown>
}

export type DashboardLayout = {
  version: 1
  globalRange: DashboardRange
  widgets: DashboardWidget[]
  updatedAt?: string
}

export type SizeUnits = { w: number; h: number }

export const SIZE_UNITS: Record<WidgetSize, SizeUnits> = {
  "1x1": { w: 3, h: 1 },
  "2x1": { w: 6, h: 1 },
  "2x2": { w: 6, h: 2 },
  "4x1": { w: 12, h: 1 },
  "4x2": { w: 12, h: 2 },
}

export const GRID_COLS = 12
