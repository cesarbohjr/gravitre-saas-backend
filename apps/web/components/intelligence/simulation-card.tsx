"use client"

import { ShieldCheck, WarningCircle } from "@phosphor-icons/react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { readString } from "@/lib/intelligence/helpers"

export function SimulationCard({
  simulation,
  className,
}: {
  simulation: Record<string, unknown> | null | undefined
  className?: string
}) {
  const status = readString(simulation?.status, "insufficient_data")
  const reversible = simulation?.reversible !== false
  const estimatedImpact = simulation?.estimated_impact
  const assumptions = Array.isArray(simulation?.assumptions)
    ? (simulation?.assumptions as string[])
    : []

  if (status === "insufficient_data" || !simulation) {
    return (
      <div
        className={cn(
          "rounded-xl border border-dashed border-border bg-secondary/40 px-4 py-4 text-sm text-muted-foreground",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <WarningCircle className="mt-0.5 h-4 w-4 shrink-0" weight="duotone" aria-hidden />
          <p className="text-pretty">
            Not enough historical runs to simulate this action yet. Estimates appear once similar
            workflows or connector actions have been observed.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("rounded-xl border border-border/70 bg-card/50 p-4", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className="capitalize">
          {status.replace(/_/g, " ")}
        </Badge>
        <Badge
          variant="outline"
          className={cn(
            reversible
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
              : "border-rose-500/30 bg-rose-500/10 text-rose-800 dark:text-rose-300",
          )}
        >
          <ShieldCheck className="mr-1 h-3.5 w-3.5" weight="duotone" aria-hidden />
          {reversible ? "Reversible" : "May be irreversible"}
        </Badge>
      </div>
      {estimatedImpact != null ? (
        <p className="mt-3 text-sm text-foreground">
          Estimated impact: {readString(estimatedImpact, "—")}
        </p>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Impact estimate unavailable — not fabricated.</p>
      )}
      {assumptions.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
          {assumptions.map((item) => (
            <li key={item}>• {item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
