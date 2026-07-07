"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { learningLevelClass, learningLevelLabel } from "@/lib/intelligence/visibility-helpers"
import type { LearningConfidenceView } from "@/lib/intelligence/visibility-types"

export function LearningConfidenceBadge({
  learning,
  className,
  showSamples = true,
}: {
  learning?: LearningConfidenceView | null
  className?: string
  showSamples?: boolean
}) {
  const level = learning?.level || "insufficient_data"
  const insufficient = learning?.insufficient_data !== false && level === "insufficient_data"

  return (
    <Badge variant="outline" className={cn("font-normal", learningLevelClass(level), className)}>
      {learningLevelLabel(level)}
      {showSamples && learning?.sample_count != null && !insufficient ? (
        <span className="ml-1 tabular-nums opacity-80">({learning.sample_count} samples)</span>
      ) : null}
    </Badge>
  )
}
