"use client"

import { HelpCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export function ClarificationMessage({
  text,
  suggestions,
  onSelectSuggestion,
}: {
  text: string
  suggestions?: string[]
  onSelectSuggestion?: (value: string) => void
}) {
  return (
    <div className="space-y-3">
      <div
        className={cn(
          "rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5",
        )}
      >
        <div className="flex items-start gap-2">
          <HelpCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <p className="text-sm leading-relaxed text-foreground">{text}</p>
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
              className="h-8 rounded-full border-amber-500/30 bg-background text-xs hover:bg-amber-500/10"
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
