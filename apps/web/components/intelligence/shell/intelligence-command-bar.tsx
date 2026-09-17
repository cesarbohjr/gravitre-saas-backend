"use client"

import { AskGravitreComposer } from "@/components/intelligence/ask-gravitre-composer"
import type { AssistantVisualization } from "@/lib/intelligence/assistant-visualization"
import { cn } from "@/lib/utils"

/**
 * I1 — shared Ask Gravitre command surface for Intelligence routes.
 * Wraps the existing composer; pages supply suggestions and visualization handlers.
 */
export function IntelligenceCommandBar({
  suggestions,
  onVisualization,
  pendingQuestion,
  onPendingQuestionConsumed,
  variant = "map",
  className,
  selected,
}: {
  suggestions?: string[] | null
  onVisualization?: (visualization: AssistantVisualization) => void
  pendingQuestion?: string | null
  onPendingQuestionConsumed?: () => void
  variant?: "map" | "card"
  className?: string
  selected?: import("@/components/gravitre/ai-workspace-provider").GravitreAISelectedEntity | null
}) {
  return (
    <AskGravitreComposer
      variant={variant}
      suggestions={suggestions}
      onVisualization={onVisualization}
      pendingQuestion={pendingQuestion}
      onPendingQuestionConsumed={onPendingQuestionConsumed}
      selected={selected}
      className={cn(className)}
    />
  )
}
