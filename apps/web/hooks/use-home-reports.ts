"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import useSWR from "swr"
import { apiFetch } from "@/lib/fetcher"
import {
  defaultReportsLayout,
  parseReportsLayout,
  presetWidgets,
  viewerTzOffsetMinutes,
  type HomeReports,
  type ReportsLayout,
  type ReportsPresetId,
  type ReportsRange,
  type ReportsWidget,
} from "@/lib/dashboard/home-reports"

const LOCAL_KEY = "gravitre:home-reports-layout:v2"

function localKey(orgId: string | null, userId: string | null) {
  return `${LOCAL_KEY}:${orgId ?? "-"}:${userId ?? "-"}`
}

function readLocal(key: string): ReportsLayout | null {
  try {
    return parseReportsLayout(JSON.parse(window.localStorage.getItem(key) ?? "null"))
  } catch {
    return null
  }
}

function writeLocal(key: string, layout: ReportsLayout) {
  try {
    window.localStorage.setItem(key, JSON.stringify(layout))
  } catch {
    // storage unavailable: the layout still saves to the account
  }
}

async function fetchReports(range: ReportsRange): Promise<HomeReports> {
  const res = await apiFetch(`/api/metrics/home-reports?range=${range}&tz=${viewerTzOffsetMinutes()}`, {
    timeoutMs: 20_000,
  })
  if (!res.ok) throw new Error(`Reports unavailable (${res.status})`)
  return (await res.json()) as HomeReports
}

/** Reports data for the chosen range, refreshed every minute while the view is open. */
export function useHomeReportsData(enabled: boolean, range: ReportsRange) {
  return useSWR<HomeReports>(enabled ? `home/reports:${range}` : null, () => fetchReports(range), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    keepPreviousData: true,
    refreshInterval: 60_000,
  })
}

/** Range, view preset and widget layout; saved locally at once and to the account in the background. */
export function useHomeReportsLayout(orgId: string | null, userId: string | null) {
  const [layout, setLayout] = useState<ReportsLayout>(() => defaultReportsLayout())
  const key = localKey(orgId, userId)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let cancelled = false
    const local = readLocal(key)
    if (local) setLayout(local)
    if (!orgId || !userId) return
    void apiFetch("/api/settings/home-reports-layout", { timeoutMs: 15_000 })
      .then(async (res) => (res.ok ? ((await res.json()) as { layout?: unknown }) : null))
      .then((body) => {
        const remote = parseReportsLayout(body?.layout)
        if (cancelled || !remote) return
        if (!local || (remote.updatedAt ?? "") >= (local.updatedAt ?? "")) {
          setLayout(remote)
          writeLocal(key, remote)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [key, orgId, userId])

  const persist = useCallback(
    (next: ReportsLayout) => {
      const stamped = { ...next, updatedAt: new Date().toISOString() }
      setLayout(stamped)
      writeLocal(key, stamped)
      if (!orgId || !userId) return
      if (saveTimer.current) clearTimeout(saveTimer.current)
      saveTimer.current = setTimeout(() => {
        void apiFetch("/api/settings/home-reports-layout", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ layout: stamped }),
        }).catch(() => undefined)
      }, 600)
    },
    [key, orgId, userId],
  )

  const widgets: ReportsWidget[] = layout.layouts[layout.preset] ?? presetWidgets(layout.preset)

  return {
    range: layout.range,
    preset: layout.preset,
    widgets,
    /** The viewer picked a view or arranged widgets, so their master view exists. */
    customized: layout.preset !== "ops" || Object.keys(layout.layouts).length > 0,
    setRange: (range: ReportsRange) => persist({ ...layout, range }),
    setPreset: (preset: ReportsPresetId) => persist({ ...layout, preset }),
    setWidgets: (list: ReportsWidget[]) =>
      persist({ ...layout, layouts: { ...layout.layouts, [layout.preset]: list } }),
    resetWidgets: () => {
      const layouts = { ...layout.layouts }
      delete layouts[layout.preset]
      persist({ ...layout, layouts })
    },
  }
}
