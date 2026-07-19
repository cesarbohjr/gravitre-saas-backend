"use client"

import useSWR from "swr"
import { motion } from "framer-motion"
import { Sparkles, ArrowRight, X, Plug, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { enterpriseApi } from "@/lib/api"
import { ESTIMATED_CONFIDENCE_SHORT } from "@/lib/outcome-labels"
import { cn } from "@/lib/utils"
import type { IntegrationSuggestion } from "@/types/api"

interface ConnectorRecommendationsProps {
  /** Called when a recommendation is acted on so the parent can open the add-connector modal pre-filtered. */
  onConnect?: (connectorType: string | null) => void
}

const CONFIDENCE_TONE = (c: number) => {
  if (c >= 0.75) return "text-chart-1 bg-chart-1/10 border-chart-1/30"
  if (c >= 0.5) return "text-chart-3 bg-chart-3/10 border-chart-3/30"
  return "text-muted-foreground bg-muted/40 border-border"
}

export function ConnectorRecommendations({ onConnect }: ConnectorRecommendationsProps) {
  const { data, error, isLoading, mutate } = useSWR(
    "integration-suggestions:connect",
    () => enterpriseApi.getIntegrationSuggestions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  // Only surface connector recommendations here; pack/automation suggestions live elsewhere.
  const suggestions = (data?.suggestions ?? [])
    .filter((s) => s.suggestionType === "connect_connector")
    .sort((a, b) => b.confidence - a.confidence || a.priority - b.priority)
    .slice(0, 4)

  const dismiss = async (id: string) => {
    // Optimistic removal, then persist.
    await mutate(
      (current) =>
        current
          ? { ...current, suggestions: current.suggestions.filter((s) => s.id !== id) }
          : current,
      { revalidate: false },
    )
    try {
      await enterpriseApi.dismissIntegrationSuggestion(id)
    } catch {
      mutate()
    }
  }

  // Render nothing if the feature has no signal — keep the hub uncluttered.
  if (error) return null
  if (isLoading) {
    return (
      <div className="border-b border-border px-4 md:px-6 py-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          Looking for recommended connectors…
        </div>
      </div>
    )
  }
  if (suggestions.length === 0) return null

  return (
    <section
      aria-label="Recommended connectors"
      className="border-b border-border bg-gradient-to-b from-primary/[0.04] to-transparent px-4 md:px-6 py-4"
    >
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/15 ring-1 ring-primary/25">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
        </div>
        <h2 className="text-sm font-semibold text-foreground">Recommended for you</h2>
        <span className="text-xs text-muted-foreground">Based on how your team works</span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {suggestions.map((s, i) => (
          <RecommendationCard
            key={s.id}
            suggestion={s}
            index={i}
            onConnect={() => onConnect?.(s.connectorType ?? null)}
            onDismiss={() => dismiss(s.id)}
          />
        ))}
      </div>
    </section>
  )
}

function RecommendationCard({
  suggestion,
  index,
  onConnect,
  onDismiss,
}: {
  suggestion: IntegrationSuggestion
  index: number
  onConnect: () => void
  onDismiss: () => void
}) {
  const confidencePct = Math.round(suggestion.confidence * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: index * 0.05 }}
      className="group relative flex flex-col rounded-xl border border-border bg-card p-3.5 transition-colors hover:border-primary/40"
    >
      <button
        type="button"
        onClick={onDismiss}
        aria-label={`Dismiss ${suggestion.title}`}
        className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground group-hover:opacity-100"
      >
        <X className="h-3.5 w-3.5" />
      </button>

      <div className="mb-2 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-secondary ring-1 ring-border">
          <Plug className="h-4 w-4 text-foreground" />
        </div>
        <span
          className={cn(
            "rounded-full border px-1.5 py-0.5 text-[10px] font-medium tabular-nums",
            CONFIDENCE_TONE(suggestion.confidence),
          )}
        >
          {ESTIMATED_CONFIDENCE_SHORT} {confidencePct}% match
        </span>
      </div>

      <h3 className="text-sm font-medium leading-snug text-foreground text-pretty">
        {suggestion.title}
      </h3>
      <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
        {suggestion.message}
      </p>

      <Button
        size="sm"
        variant="outline"
        className="mt-3 h-8 w-full justify-between gap-2"
        onClick={onConnect}
      >
        Connect
        <ArrowRight className="h-3.5 w-3.5" />
      </Button>
    </motion.div>
  )
}
