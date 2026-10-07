"use client"

/**
 * Models v2 — "Suggested by Gravitre". Rendered only for a real candidate: a
 * built-in model that runs on rules today but already has the minimum
 * examples (training-readiness API) to train for real.
 */
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { Button } from "@/components/ui/button"
import type { BuiltInModelListItem } from "@/lib/built-in-model-catalog"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

function humanize(value: string): string {
  const s = value.replace(/_/g, " ").trim()
  return s.charAt(0).toUpperCase() + s.slice(1)
}

export function ModelSuggestionCard({
  item,
  onDismiss,
}: {
  item: BuiltInModelListItem
  onDismiss: (id: string) => void
}) {
  const { summonWorkspace } = useGravitreAIWorkspace()
  const { available, required } = item.sufficiency

  return (
    <article
      className="flex flex-col gap-3.5 rounded-[var(--g-radius-panel)] border-[1.5px] border-dashed border-[color:var(--g-border-strong)] bg-[color:var(--g-canvas)] p-5 sm:p-[22px]"
      data-review-surface="models-suggestion"
      aria-labelledby={`suggestion-${item.id}`}
    >
      <span className="flex items-center gap-2 text-xs font-medium text-[color:var(--g-emerald-deep)] dark:text-[color:var(--g-brand)]">
        <NucleoIntelligence className="h-4 w-4" aria-hidden />
        Suggested by Gravitre
      </span>
      <h3 id={`suggestion-${item.id}`} className={TYPE.cardTitle}>
        {item.guide.label}
      </h3>
      <p className="text-[13px] leading-relaxed text-[color:var(--g-text-secondary)]">
        {item.guide.summary} It runs on rules today, and you now have {available.toLocaleString()} of the{" "}
        {required.toLocaleString()} examples it needs to learn from your own data. Gravitre can draft the training
        plan, pick the data and show you a test before anything goes live.
      </p>
      {item.useCases.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {item.useCases.slice(0, 4).map((useCase) => (
            <span
              key={useCase}
              className={cn(
                "rounded-md border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-2 py-1 text-xs",
                "text-[color:var(--g-intelligence)]",
              )}
            >
              {humanize(useCase)}
            </span>
          ))}
        </div>
      ) : null}
      <div className="flex-1" />
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() =>
            summonWorkspace({
              presentation: "compact",
              selected: { kind: "built_in_model", id: item.id, label: item.guide.label },
              agentScope: null,
              composerText: `Draft a plan to train the built-in "${item.guide.label}" model on our own data. Say which examples it would learn from, how we would test it offline, and what has to be true before it goes live.`,
              submit: false,
            })
          }
        >
          Draft it with Gravitre
        </Button>
        <Button variant="ghost" onClick={() => onDismiss(item.id)}>
          Not now
        </Button>
      </div>
    </article>
  )
}
