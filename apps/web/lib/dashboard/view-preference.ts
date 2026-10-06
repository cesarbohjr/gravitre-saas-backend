"use client"

import { useCallback, useEffect, useState } from "react"

/**
 * Home dashboard view: the AI Native operating briefing (default) or the Reports
 * board of configured KPIs. Per-viewer convenience only, so it lives in localStorage
 * and falls back to the default when storage is unavailable.
 */
export type DashboardView = "ai" | "reports"

export const DEFAULT_DASHBOARD_VIEW: DashboardView = "ai"

const VIEW_KEY = "gravitre:dashboard-view:v1"

export function parseDashboardView(raw: unknown): DashboardView {
  return raw === "reports" ? "reports" : DEFAULT_DASHBOARD_VIEW
}

function readPref(key: string): string | null {
  if (typeof window === "undefined") return null
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writePref(key: string, value: string): void {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // private mode / blocked storage: the choice just won't persist
  }
}

export function useDashboardView(): [DashboardView, (view: DashboardView) => void] {
  const [view, setViewState] = useState<DashboardView>(DEFAULT_DASHBOARD_VIEW)
  useEffect(() => {
    setViewState(parseDashboardView(readPref(VIEW_KEY)))
  }, [])
  const setView = useCallback((next: DashboardView) => {
    setViewState(next)
    writePref(VIEW_KEY, next)
  }, [])
  return [view, setView]
}

/** Remembered open/closed state for a collapsible dashboard section. */
export function useSectionCollapsed(sectionId: string, defaultCollapsed = false): [boolean, () => void] {
  const key = `gravitre:dashboard-section:${sectionId}:collapsed`
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  useEffect(() => {
    const stored = readPref(key)
    if (stored === "1" || stored === "0") setCollapsed(stored === "1")
  }, [key])
  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      writePref(key, prev ? "0" : "1")
      return !prev
    })
  }, [key])
  return [collapsed, toggle]
}
