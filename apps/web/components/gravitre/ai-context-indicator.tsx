"use client"

import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  formatGravitreAiContextLabel,
  gravitreAiContextHasVisibleState,
} from "@/lib/gravitre-ai-context-label"
import { useGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"

export function GravitreAIContextIndicator({ className }: { className?: string }) {
  const { agentScope, pageContext, clearSelectedEntity } = useGravitreAIWorkspace()
  const label = formatGravitreAiContextLabel({
    agentName: agentScope?.name,
    selectedKind: pageContext.selected?.kind,
    selectedLabel: pageContext.selected?.label,
  })

  if (!gravitreAiContextHasVisibleState(label)) return null

  return (
    <p
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] font-medium text-[color:var(--g-text-secondary)]",
        className,
      )}
      data-gravitre-ai-context=""
    >
      {label.agentLine ? <span className="truncate">{label.agentLine}</span> : null}
      {label.agentLine && label.selectionLine ? (
        <span aria-hidden className="text-[color:var(--g-text-tertiary)]">
          ·
        </span>
      ) : null}
      {label.selectionLine ? (
        <span className="inline-flex min-w-0 items-center gap-1">
          <span className="truncate">{label.selectionLine}</span>
          <button
            type="button"
            className="shrink-0 rounded-sm p-0.5 text-[color:var(--g-text-tertiary)] hover:text-[color:var(--g-text-primary)]"
            aria-label="Clear selected object"
            onClick={(event) => {
              event.stopPropagation()
              clearSelectedEntity()
            }}
          >
            <X className="h-3 w-3" aria-hidden />
          </button>
        </span>
      ) : null}
    </p>
  )
}
