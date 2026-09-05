"use client"

/**
 * Agent Elements–inspired QuestionTool chrome (ADAPT).
 * Wraps existing clarify copy — no new dialogue capability; suggestions only when provided.
 */

import { HelpCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { RADIUS, STATUS, TYPE } from "@/lib/design-system"
import { Button } from "@/components/ui/button"

export function ClarificationMessage({
  text,
  children,
  suggestions,
  onSelectSuggestion,
  className,
}: {
  text?: string
  children?: React.ReactNode
  suggestions?: string[]
  onSelectSuggestion?: (value: string) => void
  className?: string
}) {
  return (
    <div className={cn("space-y-3", className)}>
      <div
        className={cn(
          "overflow-hidden border bg-card",
          RADIUS.card,
          "border-[color:var(--status-pending)]/30",
        )}
      >
        <div
          className={cn(
            "flex h-8 items-center gap-1.5 border-b border-border px-3",
            STATUS.pending,
            "rounded-none border-x-0 border-t-0",
          )}
        >
          <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden />
          <span className={cn(TYPE.meta, "font-medium")}>Clarifying</span>
        </div>
        <div className="space-y-2 bg-background px-3 py-2.5">
          {children ? children : text ? <p className="text-sm leading-relaxed text-foreground">{text}</p> : null}
        </div>
      </div>
      {suggestions && suggestions.length > 0 && onSelectSuggestion ? (
        <div className="flex flex-wrap gap-2">
          {suggestions.slice(0, 3).map((suggestion) => (
            <Button
              key={suggestion}
              type="button"
              variant="outline"
              size="sm"
              className={cn(
                "h-8 text-xs",
                RADIUS.control,
                "border-[color:var(--status-pending)]/30 hover:bg-[color:var(--status-pending)]/10",
              )}
              onClick={() => onSelectSuggestion(suggestion)}
            >
              {suggestion}
            </Button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
