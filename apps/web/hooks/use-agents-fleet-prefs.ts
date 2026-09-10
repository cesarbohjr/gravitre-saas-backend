"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  DEFAULT_AGENTS_FLEET_PREFS,
  fetchRemoteAgentsFleetPrefs,
  readLocalAgentsFleetPrefs,
  saveRemoteAgentsFleetPrefs,
  writeLocalAgentsFleetPrefs,
  type AgentsFleetFilters,
  type AgentsFleetPrefs,
  type AgentsFleetSortId,
  type AgentsFleetViewPref,
} from "@/lib/agents-fleet-prefs"

/**
 * Fleet view/sort/filter prefs — localStorage first, then remote merge.
 * Documented fallback: if /api/settings/agents-fleet fails, localStorage still works.
 */
export function useAgentsFleetPrefs() {
  const [prefs, setPrefs] = useState<AgentsFleetPrefs>(() => {
    if (typeof window === "undefined") return DEFAULT_AGENTS_FLEET_PREFS
    return readLocalAgentsFleetPrefs() ?? DEFAULT_AGENTS_FLEET_PREFS
  })
  const [hydrated, setHydrated] = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let cancelled = false
    const local = readLocalAgentsFleetPrefs()
    if (local) setPrefs(local)

    void (async () => {
      const remote = await fetchRemoteAgentsFleetPrefs()
      if (cancelled) return
      if (remote) {
        setPrefs(remote)
        writeLocalAgentsFleetPrefs(remote)
      }
      setHydrated(true)
    })()

    return () => {
      cancelled = true
    }
  }, [])

  const persist = useCallback((next: AgentsFleetPrefs) => {
    writeLocalAgentsFleetPrefs(next)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      void saveRemoteAgentsFleetPrefs(next)
    }, 400)
  }, [])

  const updatePrefs = useCallback(
    (patch: Partial<AgentsFleetPrefs> | ((prev: AgentsFleetPrefs) => AgentsFleetPrefs)) => {
      setPrefs((prev) => {
        const next =
          typeof patch === "function"
            ? patch(prev)
            : {
                ...prev,
                ...patch,
                filters: patch.filters ? { ...prev.filters, ...patch.filters } : prev.filters,
                version: 1 as const,
              }
        persist(next)
        return next
      })
    },
    [persist],
  )

  const setView = useCallback(
    (view: AgentsFleetViewPref) => updatePrefs({ view }),
    [updatePrefs],
  )

  const setSort = useCallback(
    (sort: AgentsFleetSortId, sortDir?: "asc" | "desc") =>
      updatePrefs((prev) => ({
        ...prev,
        sort,
        sortDir:
          sortDir ??
          (prev.sort === sort ? prev.sortDir : "asc"),
      })),
    [updatePrefs],
  )

  const toggleSortDir = useCallback(
    () =>
      updatePrefs((prev) => ({
        ...prev,
        sortDir: prev.sortDir === "asc" ? "desc" : "asc",
      })),
    [updatePrefs],
  )

  const setFilters = useCallback(
    (filters: Partial<AgentsFleetFilters>) =>
      updatePrefs((prev) => ({
        ...prev,
        filters: { ...prev.filters, ...filters },
      })),
    [updatePrefs],
  )

  const clearFilters = useCallback(
    () =>
      updatePrefs({
        filters: { department: null, status: null, role: null, model: null },
      }),
    [updatePrefs],
  )

  return {
    prefs,
    hydrated,
    setView,
    setSort,
    toggleSortDir,
    setFilters,
    clearFilters,
    updatePrefs,
  }
}
