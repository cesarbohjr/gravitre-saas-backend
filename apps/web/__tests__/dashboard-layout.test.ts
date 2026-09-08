import { describe, expect, it } from "vitest"
import { normalizeMetricsOverview } from "@/lib/dashboard/normalize-metrics"
import { packWidgets, moveWidgetOrder } from "@/lib/dashboard/place-widgets"
import { createDefaultLayout } from "@/lib/dashboard/kpi-registry"
import type { DashboardWidget } from "@/lib/dashboard/types"

describe("normalizeMetricsOverview", () => {
  it("prefers camelCase live API fields", () => {
    const n = normalizeMetricsOverview({
      totalRuns: 12,
      successRate: 96.7,
      avgDuration: 1500,
      activeWorkflows: 3,
      trends: { totalRuns: [1, 2, 3] },
    })
    expect(n.totalRuns).toBe(12)
    expect(n.successRate).toBe(96.7)
    expect(n.avgDuration).toBe(1500)
    expect(n.activeWorkflows).toBe(3)
    expect(n.trends.totalRuns).toEqual([1, 2, 3])
  })

  it("falls back to snake_case legacy keys", () => {
    const n = normalizeMetricsOverview({
      total_runs: 4,
      avg_run_duration_ms: 900,
      active_workflows: 1,
    })
    expect(n.totalRuns).toBe(4)
    expect(n.avgDuration).toBe(900)
    expect(n.activeWorkflows).toBe(1)
  })
})

describe("packWidgets", () => {
  it("places default Nodus layout without overlap", () => {
    const layout = createDefaultLayout()
    const placed = packWidgets(layout.widgets)
    expect(placed).toHaveLength(7)
    // Four 1x1 KPIs on row 0
    expect(placed.filter((p) => p.y === 0)).toHaveLength(4)
    // Monitor full width below
    const monitor = placed.find((p) => p.metricId === "agents.monitor")
    expect(monitor?.w).toBe(12)
    expect(monitor?.y).toBe(1)
  })

  it("reflows after reorder", () => {
    const widgets: DashboardWidget[] = createDefaultLayout().widgets
    const moved = moveWidgetOrder(widgets, widgets[0].id, 3)
    const placed = packWidgets(moved)
    expect(placed[0].order).toBe(0)
    expect(new Set(placed.map((p) => `${p.x},${p.y},${p.w},${p.h}`)).size).toBe(placed.length)
  })
})

describe("dashboard presets", () => {
  it("builds layouts from registry metrics only", async () => {
    const { DASHBOARD_PRESETS, KPI_BY_ID } = await import("@/lib/dashboard/kpi-registry")
    expect(DASHBOARD_PRESETS.length).toBeGreaterThanOrEqual(5)
    for (const preset of DASHBOARD_PRESETS) {
      const layout = preset.build()
      expect(layout.version).toBe(1)
      expect(layout.widgets.length).toBeGreaterThan(0)
      for (const w of layout.widgets) {
        expect(KPI_BY_ID[w.metricId]).toBeTruthy()
      }
    }
  })
})
