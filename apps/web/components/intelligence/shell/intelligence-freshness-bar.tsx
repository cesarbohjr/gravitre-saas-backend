"use client"

import { DataFreshness } from "@/components/gravitre/data-freshness"
import {
  snapshotLoadStateLabel,
  type SnapshotLoadState,
} from "@/lib/intelligence/snapshot-state"
import { cn } from "@/lib/utils"

export function IntelligenceFreshnessBar({
  loadState,
  generatedAt,
  isValidating,
  onRefresh,
  className,
}: {
  loadState: SnapshotLoadState
  generatedAt?: string | null
  isValidating?: boolean
  onRefresh?: () => void
  className?: string
}) {
  const isRefreshing = loadState === "REFRESHING" || Boolean(isValidating)
  const showTimestamp =
    loadState === "READY" ||
    loadState === "REFRESHING" ||
    loadState === "DEGRADED"

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground",
        className,
      )}
    >
      <DataFreshness
        updatedAt={showTimestamp ? generatedAt : null}
        isRefreshing={isRefreshing}
        onRefresh={onRefresh}
        label={loadState === "READY" ? "Updated" : snapshotLoadStateLabel(loadState)}
      />
      {loadState === "DEGRADED" ? (
        <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-amber-700 dark:text-amber-300">
          Some sources unavailable
        </span>
      ) : null}
      {loadState === "ERROR" ? (
        <span className="text-destructive">{snapshotLoadStateLabel(loadState)}</span>
      ) : null}
    </div>
  )
}
