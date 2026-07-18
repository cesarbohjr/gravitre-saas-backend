/** Adaptive research scope prompt when internal retrieval is thin. */
"use client"

import { cn } from "@/lib/utils"
import type { ResearchCascadePayload, ResearchScopeOption } from "./research-cascade-types"

export type { ResearchCascadePayload, ResearchScopeOption }

type ResearchScopePromptProps = {
  cascade: ResearchCascadePayload | null | undefined
  onSelectScope: (scope: string) => void
  className?: string
}

export function ResearchScopePrompt({ cascade, onSelectScope, className }: ResearchScopePromptProps) {
  if (!cascade?.suggest_broaden || !cascade.prompt_message) return null
  const options = cascade.options ?? []
  if (options.length === 0) return null

  return (
    <div
      className={cn(
        "rounded-xl border border-emerald-500/20 bg-emerald-50/40 px-4 py-3 text-sm dark:bg-emerald-950/20",
        className,
      )}
    >
      <p className="text-foreground leading-relaxed">{cascade.prompt_message}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        Choose how far to broaden research for this question.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.scope}
            type="button"
            disabled={!option.enabled}
            title={option.disabled_reason ?? option.description}
            onClick={() => option.enabled && onSelectScope(option.scope)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-left text-xs transition-colors",
              option.enabled
                ? "border-emerald-600/30 bg-white hover:bg-emerald-50 dark:bg-card dark:hover:bg-emerald-950/40"
                : "cursor-not-allowed border-border/60 bg-muted/40 text-muted-foreground opacity-70",
            )}
          >
            <span className="font-medium">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
