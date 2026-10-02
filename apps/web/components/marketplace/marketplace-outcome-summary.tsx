"use client"

import { Badge } from "@/components/ui/badge"
import { CheckCircle2, Gauge, TrendingDown, TrendingUp } from "lucide-react"
import type { MarketplaceAssetSummary, MarketplaceKpiImpact } from "@/types/api"
import { cn } from "@/lib/utils"

function verificationLabel(level?: string | null): string {
  switch (level) {
    case "outcome_verified":
      return "Outcome verified"
    case "production_verified":
      return "Production verified"
    case "governed":
      return "Governed"
    case "tested":
      return "Tested"
    case "compatible":
      return "Compatible"
    default:
      return "Unverified"
  }
}

function kpiDirectionIcon(kpi: MarketplaceKpiImpact) {
  if (kpi.direction === "decrease") return TrendingDown
  if (kpi.direction === "increase") return TrendingUp
  return Gauge
}

export function MarketplaceOutcomeSummary({
  asset,
  compact = false,
}: {
  asset: MarketplaceAssetSummary
  compact?: boolean
}) {
  const outcome = asset.outcomeTarget || asset.businessOutcome
  const kpis = asset.kpiImpact ?? []
  const ready = Boolean(asset.installReady ?? asset.canInstall)
  const hasOutcomeData = Boolean(
    outcome ||
      kpis.length ||
      asset.verificationLevel ||
      asset.estimatedHoursSaved != null ||
      asset.playCount,
  )

  if (!hasOutcomeData) return null

  return (
    <div className={cn("space-y-2", compact && "space-y-1.5")}>
      {outcome ? (
        <p className={cn(
          "text-pretty font-medium leading-snug text-foreground",
          compact ? "line-clamp-2 text-[12.5px]" : "text-sm",
        )}>
          {outcome}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-1.5">
        {asset.verificationLevel ? (
          <Badge variant="outline" className="gap-1 text-[10px]">
            <CheckCircle2 className="h-3 w-3" aria-hidden />
            {verificationLabel(asset.verificationLevel)}
          </Badge>
        ) : null}
        <Badge variant={ready ? "secondary" : "outline"} className="text-[10px]">
          {asset.installed ? "Installed" : ready ? "Ready to install" : "Setup required"}
        </Badge>
        {asset.playCount ? (
          <Badge variant="outline" className="text-[10px]">
            {asset.playCount} Plays
          </Badge>
        ) : null}
        {asset.estimatedHoursSaved != null ? (
          <Badge variant="outline" className="text-[10px]">
            ~{asset.estimatedHoursSaved}h/mo potential
          </Badge>
        ) : null}
      </div>

      {kpis.length ? (
        <div className={cn("flex flex-wrap gap-1.5", !compact && "gap-2")}>
          {kpis.slice(0, compact ? 3 : 6).map((kpi) => {
            const Icon = kpiDirectionIcon(kpi)
            return (
              <span
                key={kpi.key}
                className="inline-flex min-w-0 items-center gap-1 rounded-md border bg-muted/20 px-2 py-1 text-[10.5px] text-muted-foreground"
                title={`${kpi.label} · ${kpi.direction}`}
              >
                <Icon className="h-3 w-3 shrink-0" aria-hidden />
                <span className="truncate">{kpi.label}</span>
              </span>
            )
          })}
          {kpis.length > (compact ? 3 : 6) ? (
            <span className="self-center text-[10.5px] text-muted-foreground">
              +{kpis.length - (compact ? 3 : 6)} KPIs
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
