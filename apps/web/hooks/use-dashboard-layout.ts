"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import type { DashboardLayout, DashboardWidget, WidgetSize } from "@/lib/dashboard/types"
import { createDefaultLayout, KPI_BY_ID } from "@/lib/dashboard/kpi-registry"
import {
  fetchRemoteLayout,
  readLocalLayout,
  saveRemoteLayout,
  writeLocalLayout,
} from "@/lib/dashboard/layout-storage"
import { moveWidgetOrder, nextSize, reindexOrders } from "@/lib/dashboard/place-widgets"

export function useDashboardLayout(orgId: string | null, userId: string | null) {
  const [layout, setLayout] = useState<DashboardLayout>(() => createDefaultLayout())
  const [editMode, setEditMode] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (!orgId || !userId) {
        setLayout(createDefaultLayout())
        setHydrated(true)
        return
      }
      const local = readLocalLayout(orgId, userId)
      if (local && !cancelled) setLayout(local)

      const remote = await fetchRemoteLayout()
      if (cancelled) return
      if (remote) {
        setLayout(remote)
        writeLocalLayout(orgId, userId, remote)
      } else if (!local) {
        setLayout(createDefaultLayout())
      }
      setHydrated(true)
    }
    void hydrate()
    return () => {
      cancelled = true
    }
  }, [orgId, userId])

  const persist = useCallback(
    async (next: DashboardLayout) => {
      setLayout(next)
      if (!orgId || !userId) return
      writeLocalLayout(orgId, userId, next)
      setSaving(true)
      try {
        await saveRemoteLayout(next)
      } finally {
        setSaving(false)
      }
    },
    [orgId, userId],
  )

  const updateWidgets = useCallback(
    (widgets: DashboardWidget[]) => {
      void persist({
        ...layout,
        widgets: reindexOrders(widgets),
        updatedAt: new Date().toISOString(),
      })
    },
    [layout, persist],
  )

  const addWidget = useCallback(
    (metricId: string) => {
      const def = KPI_BY_ID[metricId]
      if (!def) return
      if (layout.widgets.some((w) => w.metricId === metricId)) return
      const widget: DashboardWidget = {
        id: `w_${metricId.replace(/\./g, "_")}_${Date.now().toString(36)}`,
        metricId,
        size: def.defaultSize,
        order: layout.widgets.length,
        visualization: def.defaultViz,
      }
      updateWidgets([...layout.widgets, widget])
    },
    [layout.widgets, updateWidgets],
  )

  const removeWidget = useCallback(
    (widgetId: string) => {
      updateWidgets(layout.widgets.filter((w) => w.id !== widgetId))
    },
    [layout.widgets, updateWidgets],
  )

  const reorderWidget = useCallback(
    (widgetId: string, toOrder: number) => {
      updateWidgets(moveWidgetOrder(layout.widgets, widgetId, toOrder))
    },
    [layout.widgets, updateWidgets],
  )

  const resizeWidget = useCallback(
    (widgetId: string) => {
      updateWidgets(
        layout.widgets.map((w) => {
          if (w.id !== widgetId) return w
          const def = KPI_BY_ID[w.metricId]
          const allowed = def?.allowedSizes ?? [w.size]
          const size = nextSize(w.size as WidgetSize, allowed)
          // Progressive reveal: bump viz when size grows into chart-capable sizes
          let visualization = w.visualization
          if ((size === "2x1" || size === "2x2") && def?.allowedViz.includes("number_trend")) {
            visualization = "number_trend"
          }
          if ((size === "2x2" || size === "4x2") && def?.allowedViz.includes("sparkline")) {
            visualization = w.visualization === "number" ? "sparkline" : w.visualization
          }
          return { ...w, size, visualization }
        }),
      )
    },
    [layout.widgets, updateWidgets],
  )

  const setRange = useCallback(
    (globalRange: DashboardLayout["globalRange"]) => {
      void persist({ ...layout, globalRange, updatedAt: new Date().toISOString() })
    },
    [layout, persist],
  )

  const resetLayout = useCallback(() => {
    void persist(createDefaultLayout())
  }, [persist])

  const displayedMetricIds = useMemo(
    () => new Set(layout.widgets.map((w) => w.metricId)),
    [layout.widgets],
  )

  return {
    layout,
    editMode,
    setEditMode,
    hydrated,
    saving,
    addWidget,
    removeWidget,
    reorderWidget,
    resizeWidget,
    setRange,
    resetLayout,
    displayedMetricIds,
  }
}
