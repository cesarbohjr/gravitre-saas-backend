"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  confidenceBand,
  confidenceBandClass,
  confidenceBandLabel,
  formatScore,
} from "@/lib/intelligence/helpers"

export function ConfidenceBadge({
  score,
  className,
  showScore = true,
}: {
  score: number | null | undefined
  className?: string
  showScore?: boolean
}) {
  const band = confidenceBand(score)
  return (
    <Badge variant="outline" className={cn("font-normal", confidenceBandClass(band), className)}>
      {confidenceBandLabel(band)}
      {showScore && score != null && !Number.isNaN(score) ? (
        <span className="ml-1 tabular-nums opacity-80">({formatScore(score)})</span>
      ) : null}
    </Badge>
  )
}
