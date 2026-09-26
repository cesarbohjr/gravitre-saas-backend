"use client"

import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

/**
 * Starter questions that open the canonical workspace with the prompt staged in
 * the composer. Never auto-submits — the operator sends it.
 */
export function AskPromptChips({
  prompts,
  className,
  layout = "wrap",
}: {
  prompts: string[]
  className?: string
  layout?: "wrap" | "stack"
}) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()
  if (prompts.length === 0) return null
  return (
    <ul
      className={cn(layout === "wrap" ? "flex flex-wrap gap-1.5" : "flex flex-col gap-1", className)}
      aria-label="Suggested questions"
    >
      {prompts.map((prompt) => (
        <li key={prompt} className={layout === "stack" ? "min-w-0" : undefined}>
          <button
            type="button"
            data-ask-prompt=""
            onClick={() =>
              summonWorkspace({
                presentation: "compact",
                composerText: prompt,
                submit: false,
                selected: pageContext.selected,
              })
            }
            className={cn(
              "group inline-flex max-w-full items-center gap-1.5 text-left text-[12.5px] text-[color:var(--g-text-primary)] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              layout === "wrap"
                ? "rounded-full border border-[color:var(--g-border-default)] bg-background px-3 py-1.5 hover:border-[color:var(--g-intelligence)]/40 hover:bg-[color:var(--g-surface-1)]"
                : "w-full rounded-[8px] px-2 py-1.5 hover:bg-[color:var(--g-surface-1)]",
            )}
          >
            <Sparkles className="size-3.5 shrink-0 text-[color:var(--g-intelligence)]" aria-hidden />
            <span className="truncate">{prompt}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}
