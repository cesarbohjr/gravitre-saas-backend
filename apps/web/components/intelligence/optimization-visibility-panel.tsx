"use client"

import { Lightbulb } from "@phosphor-icons/react"
import { Badge } from "@/components/ui/badge"
import { readString } from "@/lib/intelligence/helpers"

export function OptimizationVisibilityPanel({
  signals,
  pendingCount,
  className,
}: {
  signals?: Array<Record<string, unknown>>
  pendingCount?: number
  className?: string
}) {
  const rows = signals ?? []
  const count = pendingCount ?? rows.length

  return (
    <div className={`rounded-2xl border border-border/70 bg-card p-4 md:p-5 ${className ?? ""}`}>
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-warning/10 text-warning">
          <Lightbulb className="h-4 w-4" weight="duotone" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-foreground">Optimization signals</h3>
          <p className="mt-1 text-xs text-muted-foreground text-pretty">
            Recommendations are advisory only — no automatic execution.
          </p>
        </div>
        <Badge variant="outline">{count > 0 ? `${count} pending` : "None pending"}</Badge>
      </div>

      {rows.length ? (
        <ul className="mt-4 space-y-2">
          {rows.slice(0, 5).map((row, index) => (
            <li key={`${readString(row.title)}-${index}`} className="rounded-lg border border-border/60 px-3 py-2 text-xs">
              <p className="font-medium text-foreground">{readString(row.title, "Optimization recommendation")}</p>
              <p className="mt-0.5 text-muted-foreground">
                {readString(row.recommendation_type, "advisory")}
                {row.segment_key ? ` · ${readString(row.segment_key)}` : ""}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">No optimization recommendations at this time.</p>
      )}

      {/* The advisory-only rule is already stated in the header copy above, so
          the trailing `advisory_only` badge here was pure repetition (and leaked
          the raw enum). */}
    </div>
  )
}
