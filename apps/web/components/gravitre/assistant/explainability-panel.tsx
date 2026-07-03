"use client"

import { useState } from "react"
import { ChevronDown, Info } from "lucide-react"
import { cn } from "@/lib/utils"

type ExplainabilityEnvelope = {
  summary?: string
  evidence?: Array<{ label?: string; kind?: string; relevance?: number }>
  confidence_note?: string
  missing_context?: string[]
}

export function ExplainabilityPanel({
  explanation,
  contextExplanation,
}: {
  explanation?: ExplainabilityEnvelope | null
  contextExplanation?: string | null
}) {
  const [expanded, setExpanded] = useState(false)
  const summary = explanation?.summary || contextExplanation
  if (!summary) return null

  return (
    <div className="mt-2 rounded-lg border border-border/70 bg-muted/30 px-3 py-2">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 text-left"
      >
        <Info className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-[11px] font-medium text-foreground">Why this answer?</span>
        <ChevronDown className={cn("ml-auto h-3.5 w-3.5 text-muted-foreground transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded ? (
        <div className="mt-2 space-y-2 text-xs text-muted-foreground">
          <p className="whitespace-pre-wrap text-foreground/90">{summary}</p>
          {explanation?.confidence_note ? <p>{explanation.confidence_note}</p> : null}
          {explanation?.evidence?.length ? (
            <ul className="space-y-1">
              {explanation.evidence.slice(0, 6).map((row) => (
                <li key={`${row.label}-${row.kind}`}>
                  {row.label}
                  {row.relevance != null ? ` (${Math.round(Number(row.relevance) * 100)}%)` : ""}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
