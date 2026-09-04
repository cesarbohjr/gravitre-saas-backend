"use client"

import { cn } from "@/lib/utils"
import {
  confidenceBand,
  confidenceBandClass,
  confidenceBandLabel,
  formatScore,
} from "@/lib/intelligence/helpers"
import { ESTIMATED_CONFIDENCE_SHORT } from "@/lib/outcome-labels"
import { STATUS } from "@/lib/design-system"

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
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-normal",
        isEstimate ? STATUS.estimate : confidenceBandClass(band),
        !isEstimate && "border border-border",
        className,
      )}
    >
      {isEstimate ? `${ESTIMATED_CONFIDENCE_SHORT} ` : null}
      {confidenceBandLabel(band)}
      {showScore && score != null && !Number.isNaN(score) ? (
        <span className="ml-1 tabular-nums opacity-80">({formatScore(score)})</span>
      ) : null}
    </span>
  )
}
