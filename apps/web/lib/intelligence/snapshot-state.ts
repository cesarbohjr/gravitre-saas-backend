import type { IntelligencePageContextResponse } from "@/lib/api"

/** Canonical Intelligence page lifecycle — UNKNOWN ≠ ZERO. */
export type SnapshotLoadState =
  | "UNINITIALIZED"
  | "LOADING"
  | "READY"
  | "REFRESHING"
  | "DEGRADED"
  | "ERROR"

const DEGRADED_QUALITY_FLAGS = new Set([
  "PARTIAL_SNAPSHOT",
  "DEGRADED_SOURCES",
  "SOURCE_UNAVAILABLE",
])

export function deriveSnapshotLoadState(input: {
  enabled: boolean
  isLoading: boolean
  isValidating: boolean
  error: unknown
  data: IntelligencePageContextResponse | undefined
  hadData: boolean
  qualityFlags?: string[]
}): SnapshotLoadState {
  const { enabled, isLoading, isValidating, error, data, hadData, qualityFlags = [] } = input

  if (!enabled) return "UNINITIALIZED"
  if (error && !hadData && !data) return "ERROR"
  if (isLoading && !hadData && !data) return "LOADING"
  if (isValidating && hadData && data) return "REFRESHING"
  if (data) {
    const degraded = qualityFlags.some((flag) => DEGRADED_QUALITY_FLAGS.has(flag))
    if (degraded || (error && hadData)) return "DEGRADED"
    return "READY"
  }
  if (error) return "ERROR"
  return "LOADING"
}

export function snapshotLoadStateLabel(state: SnapshotLoadState): string {
  switch (state) {
    case "UNINITIALIZED":
      return "Not yet loaded"
    case "LOADING":
      return "Loading intelligence…"
    case "READY":
      return "Live"
    case "REFRESHING":
      return "Refreshing…"
    case "DEGRADED":
      return "Some sources unavailable"
    case "ERROR":
      return "Unable to load"
  }
}

export function isSnapshotMetricsReady(state: SnapshotLoadState): boolean {
  return state === "READY" || state === "REFRESHING" || state === "DEGRADED"
}
