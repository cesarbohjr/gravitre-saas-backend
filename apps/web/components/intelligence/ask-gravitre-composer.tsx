"use client"

/**
 * Ask Gravitre — entry that summons the canonical AI workspace.
 *
 * UX Reset 1.0 Phase 1A: this is NOT a chat runtime. It must not call the AI SDK chat hook.
 * It captures page/selection context, opens compact over the current page,
 * and optionally focuses or submits through the canonical composer.
 */

import { useCallback, useEffect, useState } from "react"
import { ArrowUp, ArrowRight } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { useGravitreAIWorkspace, type GravitreAISelectedEntity } from "@/components/gravitre/ai-workspace-provider"
import type { AssistantVisualization } from "@/lib/intelligence/assistant-visualization"

export { useAskGravitreSuggestions } from "@/components/intelligence/ask-gravitre-entry"

const FALLBACK_QUESTIONS = ["What changed today?", "What needs attention?", "What have you learned?"]

export function AskGravitreComposer({
  suggestions,
  className,
  variant = "card",
  onAsk,
  pendingQuestion,
  onPendingQuestionConsumed,
  selected,
}: {
  suggestions: string[] | null | undefined
  className?: string
  variant?: "card" | "map"
  onAsk?: (question: string) => void
  /** Kept so Intelligence map callers type-check; visualization is handled by the canonical runtime. */
  onVisualization?: (visualization: AssistantVisualization) => void
  pendingQuestion?: string | null
  onPendingQuestionConsumed?: () => void
  selected?: GravitreAISelectedEntity | null
}) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  const questions = suggestions?.length ? suggestions.slice(0, 3) : FALLBACK_QUESTIONS
  const usingFallback = !suggestions?.length
  const [input, setInput] = useState("")

  const summon = useCallback(
    (text: string, submit: boolean) => {
      const trimmed = text.trim()
      onAsk?.(trimmed)
      summonWorkspace({
        presentation: "compact",
        composerText: trimmed || undefined,
        submit: submit && Boolean(trimmed),
        selected: selected ?? pageContext.selected,
        agentScope: null,
      })
    },
    [onAsk, pageContext.selected, selected, summonWorkspace],
  )

  useEffect(() => {
    const trimmed = pendingQuestion?.trim()
    if (!trimmed) return
    summon(trimmed, true)
    onPendingQuestionConsumed?.()
  }, [onPendingQuestionConsumed, pendingQuestion, summon])

  const isMap = variant === "map"

  return (
    <section
      className={cn(isMap ? "p-0" : "py-1", className)}
      aria-labelledby="ask-gravitre-heading"
      data-ask-gravitre-composer=""
      data-ask-gravitre-entry=""
    >
      <p id="ask-gravitre-heading" className={isMap ? "sr-only" : cn(TYPE.sectionTitle, "mb-3")}>
        Ask Gravitre
      </p>

      <div className={cn("flex flex-col gap-1.5", isMap ? "mb-3" : "mb-3")}>
        {questions.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => summon(question, true)}
            className="text-left text-xs text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-brand)] hover:underline"
          >
            {question}
          </button>
        ))}
      </div>

      <form
        className={cn("flex gap-2", isMap ? "" : "mt-4")}
        onSubmit={(event) => {
          event.preventDefault()
          summon(input, true)
          setInput("")
        }}
      >
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={isMap ? "Ask Gravitre anything about your business…" : "Ask a question…"}
          aria-label="Ask Gravitre"
          className={isMap ? "h-11 border-[color:var(--g-brand-border)]/40 bg-background/80" : undefined}
        />
        <Button
          type="submit"
          size="icon"
          disabled={!input.trim()}
          aria-label="Ask Gravitre"
        >
          <ArrowUp className="h-4 w-4" />
        </Button>
      </form>

      {usingFallback && !isMap ? (
        <p className={cn(TYPE.meta, "mt-3")}>
          Showing example questions — a live daily briefing wasn&apos;t available for this org yet.
        </p>
      ) : null}

      <div className={cn(isMap ? "mt-2" : "mt-4")}>
        <button
          type="button"
          onClick={() => summon("", false)}
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open Gravitre
          <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    </section>
  )
}
