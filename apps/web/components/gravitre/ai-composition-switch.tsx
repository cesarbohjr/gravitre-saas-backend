"use client"

import { useId } from "react"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  AI_WORKSPACE_COMPOSITIONS,
  isAiWorkspaceComposition,
  type AiWorkspaceComposition,
  type ResolvedComposition,
} from "@/lib/gravitre-ai-composition"
import { cn } from "@/lib/utils"

const LABEL: Record<AiWorkspaceComposition, string> = {
  conversation: "Conversation",
  work: "Work",
  split: "Split",
}

const REASON: Record<NonNullable<ResolvedComposition["reason"]>, string> = {
  "no-work": "Work and Split appear once this conversation produces work.",
  "approval-visible": "Work view is paused while an approval is waiting, so the approval stays visible.",
}

/**
 * Conversation / Work / Split segmented control. Radix ToggleGroup gives roving
 * focus (arrow keys) and pressed state. Unavailable compositions are disabled, not
 * hidden, so the layout does not jump when work appears.
 */
export function GravitreAICompositionSwitch({
  resolved,
  onChange,
  className,
}: {
  resolved: ResolvedComposition
  onChange: (composition: AiWorkspaceComposition) => void
  className?: string
}) {
  const reasonId = useId()
  // A switch with one usable option is not a choice. Before any work exists it
  // only adds two dead controls to the header, so it appears with the first artifact.
  if (resolved.available.length < 2) return null
  const reason = resolved.reason
  const describedBy = reason ? reasonId : undefined
  return (
    <div className={cn("flex min-w-0 items-center gap-2", className)} data-gravitre-ai-composition={resolved.composition}>
      <ToggleGroup
        type="single"
        size="sm"
        variant="outline"
        value={resolved.composition}
        onValueChange={(value) => {
          if (isAiWorkspaceComposition(value)) onChange(value)
        }}
        aria-label="Workspace layout"
        aria-describedby={describedBy}
        className="h-7"
      >
        {AI_WORKSPACE_COMPOSITIONS.map((composition) => (
          <ToggleGroupItem
            key={composition}
            value={composition}
            disabled={!resolved.available.includes(composition)}
            className="h-7 px-2.5 text-[11px]"
          >
            {LABEL[composition]}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      {reason ? (
        <span id={reasonId} className="sr-only">
          {REASON[reason]}
        </span>
      ) : null}
    </div>
  )
}
