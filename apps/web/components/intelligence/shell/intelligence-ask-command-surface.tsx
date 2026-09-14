"use client"

/**
 * I4 — Ask Gravitre as intelligence command surface on Overview.
 * Merges daily briefing suggestions with canonical page-context questions.
 */
import { useMemo } from "react"
import { IntelligenceCommandBar } from "@/components/intelligence/shell/intelligence-command-bar"
import { useAskGravitreSuggestions } from "@/components/intelligence/ask-gravitre-composer"
import type { AssistantVisualization } from "@/lib/intelligence/assistant-visualization"

const FALLBACK_QUESTIONS = [
  "What changed today?",
  "What needs attention?",
  "What has Gravitre learned?",
  "Which agents are active?",
]

export function IntelligenceAskCommandSurface({
  enabled,
  pageSuggestedQuestions,
  onVisualization,
  pendingQuestion,
  onPendingQuestionConsumed,
}: {
  enabled: boolean
  pageSuggestedQuestions?: string[]
  onVisualization?: (visualization: AssistantVisualization) => void
  pendingQuestion?: string | null
  onPendingQuestionConsumed?: () => void
}) {
  const { data: dailyBriefing } = useAskGravitreSuggestions(enabled)

  const suggestions = useMemo(() => {
    const merged: string[] = []
    const seen = new Set<string>()
    for (const q of pageSuggestedQuestions ?? []) {
      const trimmed = q.trim()
      if (!trimmed || seen.has(trimmed)) continue
      seen.add(trimmed)
      merged.push(trimmed)
    }
    for (const q of dailyBriefing?.suggestions ?? FALLBACK_QUESTIONS) {
      const trimmed = q.trim()
      if (!trimmed || seen.has(trimmed)) continue
      seen.add(trimmed)
      merged.push(trimmed)
    }
    return merged.slice(0, 6)
  }, [pageSuggestedQuestions, dailyBriefing?.suggestions])

  return (
    <IntelligenceCommandBar
      variant="map"
      suggestions={suggestions}
      onVisualization={onVisualization}
      pendingQuestion={pendingQuestion}
      onPendingQuestionConsumed={onPendingQuestionConsumed}
    />
  )
}
