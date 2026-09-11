"use client"

import useSWR from "swr"
import { intelligenceApi } from "@/lib/api"

/**
 * Phase 2 (2026-09-11): polls the real Intelligence Core state endpoint.
 * 20s refresh — a real cadence, not a claim of sub-second live push. The
 * endpoint itself is a plain GET over live tables, so this hook never
 * fabricates data between polls; it just re-reads the same real snapshot.
 */
export function useIntelligenceCoreState(enabled: boolean, windowHours = 24) {
  return useSWR(
    enabled ? ["intelligence/core-state", windowHours] : null,
    () => intelligenceApi.coreState({ windowHours }),
    { revalidateOnFocus: false, refreshInterval: 20_000 },
  )
}
