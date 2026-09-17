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
}: {
  selected?: GravitreAISelectedEntity | null
  className?: string
}) {
  const { summonWorkspace, pageContext } = useGravitreAIWorkspace()

  return (
    <button
      type="button"
      data-ask-gravitre-summon=""
      className={cn(
        "h-8 shrink-0 text-xs font-medium text-[color:var(--g-brand)] hover:underline",
        className,
      )}
      onClick={() =>
        summonWorkspace({
          presentation: "compact",
          selected: selected ?? pageContext.selected,
          agentScope: null,
        })
      }
    >
      Ask Gravitre
    </button>
  )
}
