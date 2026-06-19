"use client"

import useSWR from "swr"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { enterpriseApi } from "@/lib/api"
import type { IntegrationSuggestion } from "@/types/api"
import { Lightbulb, X } from "lucide-react"

async function fetchSuggestionById(suggestionId: string): Promise<IntegrationSuggestion | null> {
  const [applied, open] = await Promise.all([
    enterpriseApi.getIntegrationSuggestions({ status: "applied" }),
    enterpriseApi.getIntegrationSuggestions({ status: "open" }),
  ])
  return (
    [...(applied.suggestions ?? []), ...(open.suggestions ?? [])].find(
      (row) => row.id === suggestionId,
    ) ?? null
  )
}

export function IntegrationSuggestionEvidenceBanner({
  suggestionId,
  onDismiss,
}: {
  suggestionId: string
  onDismiss: () => void
}) {
  const { data: suggestion } = useSWR(["integration-suggestion-evidence", suggestionId], () =>
    fetchSuggestionById(suggestionId),
  )

  if (!suggestion) return null

  const highlights = Object.entries(suggestion.evidence ?? {})
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)

  return (
    <div className="mb-4 flex flex-col gap-3 rounded-lg border border-primary/25 bg-primary/5 p-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-2 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Lightbulb className="h-4 w-4 text-primary shrink-0" aria-hidden />
          <p className="text-sm font-medium text-foreground">Applied recommendation context</p>
          <Badge variant="outline" className="capitalize">
            {suggestion.suggestionType.replace(/_/g, " ")}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{suggestion.message}</p>
        {highlights.length > 0 ? (
          <ul className="text-xs text-muted-foreground space-y-0.5">
            {highlights.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}
      </div>
      <Button variant="ghost" size="sm" className="shrink-0 self-start" onClick={onDismiss}>
        <X className="h-4 w-4 mr-1" />
        Dismiss
      </Button>
    </div>
  )
}
