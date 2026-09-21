import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import type { SnapshotLoadState } from "@/lib/intelligence/snapshot-state"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"

export function resolveOverviewFieldState({
  snapshotLoadState,
  activeLens,
  knownEntities,
  knownRels,
  graphNodes,
}: {
  snapshotLoadState: SnapshotLoadState
  activeLens: IntelligenceMapLens
  knownEntities: number | null
  knownRels: number | null
  graphNodes: number
}): {
  mapLoading: boolean
  isError: boolean
  isEmpty: boolean
  isSparse: boolean
  showMap: boolean
} {
  const mapLoading = !isSnapshotMetricsReady(snapshotLoadState) && snapshotLoadState !== "ERROR"
  const isError = snapshotLoadState === "ERROR"
  const isEmpty =
    !mapLoading &&
    !isError &&
    (knownEntities === 0 || knownEntities == null) &&
    (knownRels === 0 || knownRels == null) &&
    graphNodes <= 1

  const isSparse =
    activeLens === "knows" &&
    !mapLoading &&
    !isError &&
    !isEmpty &&
    typeof knownRels === "number" &&
    knownRels > 0 &&
    knownEntities === 0

  const showMap = !isError && !mapLoading && !isEmpty && !isSparse

  return { mapLoading, isError, isEmpty, isSparse, showMap }
}
