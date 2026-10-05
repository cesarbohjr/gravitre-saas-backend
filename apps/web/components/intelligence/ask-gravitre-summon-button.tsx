"use client"

import { cn } from "@/lib/utils"
import {
  useGravitreAIWorkspace,
  type GravitreAISelectedEntity,
} from "@/components/gravitre/ai-workspace-provider"

/** Header entry: opens compact canonical workspace. Not a chat runtime. */
export function AskGravitreSummonButton({
  selected,
  className,
  label = "Ask Gravitre",
  prompt,
}: {
  selected?: GravitreAISelectedEntity | null
  className?: string
  label?: string
  prompt?: string
}) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()

  return (
    <button
      type="button"
      data-ask-gravitre-summon=""
      className={cn(
        "min-h-11 shrink-0 rounded px-1 text-xs font-medium text-[color:var(--g-brand-active)] hover:underline dark:text-[color:var(--g-brand)]",
        className,
      )}
      onClick={() =>
        summonWorkspace({
          presentation: "compact",
          selected: selected ?? pageContext.selected,
          agentScope: null,
          composerText: prompt,
          submit: false,
        })
      }
    >
      {label}
    </button>
  )
}
