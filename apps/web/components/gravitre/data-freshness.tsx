"use client"

import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { RefreshCw } from "lucide-react"

interface DataFreshnessProps {
  /** Timestamp of the last successful data fetch */
  updatedAt?: Date | string | number | null
  /** Whether a refresh/revalidation is currently in flight */
  isRefreshing?: boolean
  /** Optional manual refresh handler — renders a refresh button when provided */
  onRefresh?: () => void
  /** Label prefix, defaults to "Updated" */
  label?: string
  /** Additional className */
  className?: string
}

function formatRelativeTime(value: Date): string {
  const diffMs = Date.now() - value.getTime()
  const diffSec = Math.round(diffMs / 1000)

  if (diffSec < 5) return "just now"
  if (diffSec < 60) return `${diffSec}s ago`

  const diffMin = Math.round(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`

  const diffHr = Math.round(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`

  const diffDay = Math.round(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`

  return value.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

/**
 * DataFreshness — a small, accessible indicator showing when data was last
 * loaded, with an optional manual refresh affordance. Self-updating relative
 * time keeps it honest without a parent re-render.
 */
export function DataFreshness({
  updatedAt,
  isRefreshing = false,
  onRefresh,
  label = "Updated",
  className,
}: DataFreshnessProps) {
  const resolved = updatedAt != null ? new Date(updatedAt) : null
  const isValid = resolved != null && !Number.isNaN(resolved.getTime())

  // Re-render every 30s so the relative label stays current.
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!isValid) return
    const interval = setInterval(() => setTick((t) => t + 1), 30_000)
    return () => clearInterval(interval)
  }, [isValid])

  return (
    <div
      className={cn(
        "inline-flex items-center gap-1.5 text-xs text-muted-foreground",
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          isRefreshing ? "bg-amber-500 animate-pulse" : isValid ? "bg-emerald-500" : "bg-muted-foreground/40",
        )}
        aria-hidden="true"
      />
      <span aria-live="polite">
        {isRefreshing
          ? "Refreshing…"
          : isValid
            ? `${label} ${formatRelativeTime(resolved!)}`
            : "Not yet loaded"}
      </span>
      {onRefresh && (
        <button
          type="button"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="ml-0.5 rounded p-0.5 text-muted-foreground/70 transition-colors hover:text-foreground disabled:opacity-50"
          aria-label="Refresh data"
        >
          <RefreshCw className={cn("h-3 w-3", isRefreshing && "animate-spin")} />
        </button>
      )}
    </div>
  )
}
