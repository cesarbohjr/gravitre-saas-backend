"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  confidenceBand,
  confidenceBandClass,
  confidenceBandLabel,
  formatScore,
} from "@/lib/intelligence/helpers"
import { ESTIMATED_CONFIDENCE_SHORT } from "@/lib/outcome-labels"

export function ConfidenceBadge({
  score,
  className,
  showScore = true,
  isEstimate = false,
}: {
  score: number | null | undefined
  className?: string
  showScore?: boolean
  /** Module C / STA-331: heuristic scores must not look like live intelligence. */
  isEstimate?: boolean
}) {
  const band = confidenceBand(score)
  return (
    <Badge variant="outline" className={cn("font-normal", confidenceBandClass(band), className)}>
      {isEstimate ? `${ESTIMATED_CONFIDENCE_SHORT} ` : null}
      {confidenceBandLabel(band)}
      {showScore && score != null && !Number.isNaN(score) ? (
        <span className="ml-1 tabular-nums opacity-80">({formatScore(score)})</span>
      ) : null}
    </Badge>
  )
}
