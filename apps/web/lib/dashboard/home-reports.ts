/**
 * Home dashboard Reports view (v3 design): widget catalog, view presets and the
 * GET /api/metrics/home-reports payload. Every number on the board comes from that
 * endpoint; widgets with no data say so instead of drawing placeholders.
 */

export type ReportsRange = "7d" | "30d" | "90d"
export const REPORTS_RANGES: ReportsRange[] = ["7d", "30d", "90d"]
export const RANGE_LONG: Record<ReportsRange, string> = {
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  "90d": "Last 90 days",
}

export type ReportsWidgetType =
  | "kpi_runs"
  | "kpi_success"
  | "kpi_latency"
  | "kpi_saved"
  | "kpi_cost"
  | "kpi_decisions"
  | "volume"
  | "success"
  | "donut"
  | "gauge"
  | "heat"
  | "funnel"
  | "monitor"

export type WidgetSpan = 1 | 2 | 4

export const REPORTS_WIDGETS: Record<ReportsWidgetType, { title: string; kind: string; span: WidgetSpan }> = {
  kpi_runs: { title: "Total runs", kind: "KPI", span: 1 },
  kpi_success: { title: "Task success rate", kind: "KPI", span: 1 },
  kpi_latency: { title: "Avg execution time", kind: "KPI", span: 1 },
  kpi_saved: { title: "Hours saved", kind: "KPI", span: 1 },
  kpi_cost: { title: "Model spend", kind: "KPI", span: 1 },
  kpi_decisions: { title: "Decisions resolved", kind: "KPI", span: 1 },
  volume: { title: "Run volume", kind: "Stacked bars", span: 2 },
  success: { title: "Success rate trend", kind: "Area line", span: 2 },
  donut: { title: "Runs by agent", kind: "Donut", span: 1 },
  gauge: { title: "Agent utilization", kind: "Gauge", span: 1 },
  heat: { title: "Activity by hour", kind: "Heatmap", span: 2 },
  funnel: { title: "Lead pipeline", kind: "Funnel", span: 2 },
  monitor: { title: "Workflow monitor", kind: "Table", span: 4 },
}

export type ReportsPresetId = "ops" | "exec" | "sales"

export const REPORTS_PRESETS: Record<ReportsPresetId, { name: string; list: Array<[ReportsWidgetType, WidgetSpan]> }> = {
  ops: {
    name: "Operations",
    list: [["kpi_runs", 1], ["kpi_success", 1], ["kpi_latency", 1], ["kpi_saved", 1], ["volume", 2], ["success", 2], ["donut", 1], ["gauge", 1], ["heat", 2], ["monitor", 4]],
  },
  exec: {
    name: "Executive",
    list: [["kpi_saved", 1], ["kpi_cost", 1], ["kpi_runs", 1], ["kpi_success", 1], ["volume", 4], ["donut", 1], ["gauge", 1], ["funnel", 2]],
  },
  sales: {
    name: "Sales pipeline",
    list: [["kpi_runs", 1], ["kpi_decisions", 1], ["kpi_success", 1], ["kpi_saved", 1], ["funnel", 2], ["volume", 2], ["monitor", 4]],
  },
}

export type ReportsWidget = { id: string; type: ReportsWidgetType; span: WidgetSpan }

/** Saved per user and org; one widget list per view preset. */
export type ReportsLayout = {
  version: 2
  range: ReportsRange
  preset: ReportsPresetId
  layouts: Partial<Record<ReportsPresetId, ReportsWidget[]>>
  updatedAt?: string
}

export function presetWidgets(preset: ReportsPresetId): ReportsWidget[] {
  return REPORTS_PRESETS[preset].list.map(([type, span], i) => ({ id: `${type}-${i}`, type, span }))
}

export function defaultReportsLayout(): ReportsLayout {
  return { version: 2, range: "7d", preset: "ops", layouts: {} }
}

const WIDGET_TYPES = new Set(Object.keys(REPORTS_WIDGETS))
const SPANS = new Set([1, 2, 4])

/** Accepts only well-formed saved layouts; anything else falls back to the defaults. */
export function parseReportsLayout(raw: unknown): ReportsLayout | null {
  if (!raw || typeof raw !== "object") return null
  const l = raw as Partial<ReportsLayout>
  if (l.version !== 2) return null
  const range = REPORTS_RANGES.includes(l.range as ReportsRange) ? (l.range as ReportsRange) : "7d"
  const preset = (l.preset && l.preset in REPORTS_PRESETS ? l.preset : "ops") as ReportsPresetId
  const layouts: ReportsLayout["layouts"] = {}
  for (const key of Object.keys(REPORTS_PRESETS) as ReportsPresetId[]) {
    const list = l.layouts?.[key]
    if (!Array.isArray(list)) continue
    layouts[key] = list.filter(
      (w): w is ReportsWidget =>
        Boolean(w) && typeof w.id === "string" && WIDGET_TYPES.has(w.type) && SPANS.has(w.span),
    )
  }
  return { version: 2, range, preset, layouts, updatedAt: l.updatedAt }
}

export function nextSpan(span: WidgetSpan): WidgetSpan {
  return span === 1 ? 2 : span === 2 ? 4 : 1
}

export function moveWidget(list: ReportsWidget[], fromId: string, toId: string): ReportsWidget[] {
  if (fromId === toId) return list
  const next = list.slice()
  const fi = next.findIndex((w) => w.id === fromId)
  if (fi < 0) return list
  const [moved] = next.splice(fi, 1)
  const ti = next.findIndex((w) => w.id === toId)
  if (ti < 0) return list
  next.splice(fi <= ti ? ti + 1 : ti, 0, moved)
  return next
}

// ---- GET /api/metrics/home-reports --------------------------------------------------------

export type HomeReportsSeries = {
  key: string
  agentId: string | null
  name: string
  model: string | null
  runs: number
  completed: number
  failed: number
  successRate: number | null
  latencyP50Sec: number | null
  lastRunAt: string | null
  spark: number[]
}

export type HomeReportsBucket = {
  start: string
  label: string
  axis: string
  bySeries: Record<string, number>
  total: number
  completed: number
  failed: number
  successRate: number | null
  medianDurationSec: number | null
}

export type HomeReports = {
  range: ReportsRange
  generatedAt: string
  weekly: boolean
  totals: {
    runs: number
    completed: number
    failed: number
    successRate: number | null
    medianDurationSec: number | null
    hoursSaved: number
    modelSpendUsd: number
    decisionsResolved: number
    modelCount: number
    agentCount: number
  }
  deltas: {
    runs: number | null
    successRate: number | null
    medianDurationSec: number | null
    hoursSaved: number | null
    modelSpendUsd: number | null
    decisionsResolved: number | null
  }
  series: HomeReportsSeries[]
  buckets: HomeReportsBucket[]
  heat: Array<{ day: string; cells: number[] }>
  utilization: { percent: number | null; executingHours: number; idleHours: number | null; agentCount: number }
  funnel: Array<{ key: string; name: string; value: number }>
}

/** Series colours, in volume order: the design's green, blue and amber, then more. */
export const SERIES_COLORS = ["#19C37D", "#2B59E0", "#E2A33A", "#7E9A7B", "#B5654A", "#5B6E7A", "#C98F5B"]
export const WORKFLOWS_COLOR = "#A3A49C"

export function seriesColor(series: HomeReportsSeries[], key: string): string {
  if (key === "workflows") return WORKFLOWS_COLOR
  const agents = series.filter((s) => s.key !== "workflows")
  const i = agents.findIndex((s) => s.key === key)
  return SERIES_COLORS[(i < 0 ? 0 : i) % SERIES_COLORS.length]
}

export function viewerTzOffsetMinutes(): number {
  return -new Date().getTimezoneOffset()
}
