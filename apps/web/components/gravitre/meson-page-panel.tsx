"use client"

import Link from "next/link"
import useSWR from "swr"
import { Lightbulb, Loader2, Sparkles, TrendingUp } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { mesonApi, type MesonInsight, type MesonSuggestion } from "@/lib/api"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

export type MesonPageId = "ai-chat" | "model-registry" | "model-detail" | "agent-detail"

function briefToInsights(brief: AdvisorBrief | null | undefined): MesonInsight[] {
  if (!brief) return []
  const items: MesonInsight[] = []
  if (brief.what_changed?.length) {
    items.push({
      id: "advisor-what-changed",
      title: "What changed",
      summary: brief.what_changed.slice(0, 3).join(" · "),
      category: brief.department ?? "operations",
    })
  }
  if (brief.why) {
    items.push({
      id: "advisor-why",
      title: "Why it matters",
      summary: brief.why,
      category: "learning",
    })
  }
  if (brief.impact_summary) {
    items.push({
      id: "advisor-impact",
      title: "Impact",
      summary: brief.impact_summary,
      category: "business",
    })
  }
  return items
}

function briefToSuggestions(brief: AdvisorBrief | null | undefined): MesonSuggestion[] {
  if (!brief?.recommended_actions?.length) return []
  return brief.recommended_actions
    .map((action, index) => ({
      id: action.id ?? `advisor-action-${index}`,
      nodeType: "advisory",
      label: (action.action ?? action.title ?? "").trim(),
      reason: action.reason ?? action.summary,
      confidence: action.confidence,
    }))
    .filter((s) => s.label.length > 0)
    .slice(0, 3)
}

function confidenceClass(confidence?: number) {
  if (confidence == null) return "border-border/70 bg-background/70"
  if (confidence >= 0.75) return "border-emerald-500/30 bg-emerald-500/5"
  return "border-amber-500/30 bg-amber-500/5"
}

export function MesonPagePanel({
  page,
  entityId,
  compact = false,
  advisorBrief,
  className,
  onSuggestionClick,
}: {
  page: MesonPageId
  entityId?: string
  compact?: boolean
  advisorBrief?: AdvisorBrief | null
  className?: string
  onSuggestionClick?: (suggestion: MesonSuggestion) => void
}) {
  const { user } = useAuth()
  const swrKey = user ? ["meson-page-context", page, entityId ?? ""] : null
  const { data, error, isLoading, isValidating } = useSWR(
    swrKey,
    () => mesonApi.pageContext({ page, entityId }),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: false,
      dedupingInterval: 120_000,
      keepPreviousData: true,
    },
  )

  const streamedInsights = briefToInsights(advisorBrief)
  const streamedSuggestions = briefToSuggestions(advisorBrief)
  const insights = [...streamedInsights, ...(data?.insights ?? [])]
    .filter((item) => item.title?.trim() && item.summary?.trim())
    .slice(0, compact ? 3 : 5)
  const suggestions = [...streamedSuggestions, ...(data?.suggestions ?? [])]
    .filter((item) => item.label?.trim())
    .slice(0, compact ? 3 : 4)

  const showEmpty = !isLoading && !error && insights.length === 0 && suggestions.length === 0
  const showInitialLoad = isLoading && !data && streamedInsights.length === 0 && streamedSuggestions.length === 0
  const showBackgroundRefresh = isValidating && !showInitialLoad && Boolean(data)

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
        <h3 className="text-sm font-semibold text-foreground">Meson</h3>
        {advisorBrief?.confidence != null ? (
          <span className="ml-auto text-[10px] text-muted-foreground">
            {Math.round(advisorBrief.confidence * 100)}% confidence
          </span>
        ) : null}
      </div>

      <section>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Meson suggests
        </p>
        {showInitialLoad ? (
          <div className="space-y-2">
            <Skeleton className={cn("w-full", compact ? "h-14" : "h-16")} />
            <Skeleton className={cn("w-full", compact ? "h-14" : "h-16")} />
          </div>
        ) : suggestions.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border/70 bg-background/50 px-3 py-2 text-xs text-muted-foreground">
            No suggestions yet — Meson learns as you use this surface.
          </p>
        ) : (
          <ul className="space-y-2">
            {suggestions.map((suggestion) => (
              <li
                key={suggestion.id}
                className={cn(
                  "rounded-lg border p-2.5",
                  confidenceClass(suggestion.confidence),
                )}
              >
                <div className="flex items-start gap-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-info/10 text-info">
                    <Lightbulb className="h-3.5 w-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    {onSuggestionClick ? (
                      <button
                        type="button"
                        onClick={() => onSuggestionClick(suggestion)}
                        className="text-left text-xs font-medium text-foreground hover:underline"
                      >
                        {suggestion.label}
                      </button>
                    ) : (
                      <p className="text-xs font-medium text-foreground">{suggestion.label}</p>
                    )}
                    {suggestion.reason ? (
                      <p className="mt-0.5 line-clamp-2 text-[10px] text-muted-foreground">
                        {suggestion.reason}
                      </p>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          Meson insights
        </p>
        {showInitialLoad ? (
          <Skeleton className={cn("w-full", compact ? "h-12" : "h-14")} />
        ) : error ? (
          <p className="text-xs text-muted-foreground">Insights unavailable right now.</p>
        ) : insights.length === 0 && showEmpty ? (
          <p className="text-xs text-muted-foreground">Monitoring — insights appear from org learning data.</p>
        ) : (
          <ul className="space-y-2">
            {insights.map((insight) => (
              <li
                key={insight.id}
                className="rounded-lg border border-border/70 bg-secondary/20 p-2.5"
              >
                <div className="flex items-start gap-2">
                  <TrendingUp className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-500" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium text-foreground">{insight.title}</p>
                    <p className="mt-0.5 line-clamp-3 text-[10px] text-muted-foreground">
                      {insight.summary}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {!compact ? (
        <p className="text-[10px] text-muted-foreground">
          Advisory only — review before acting.{" "}
          <Link href="/intelligence" className="text-primary underline-offset-4 hover:underline">
            Intelligence Center
          </Link>
        </p>
      ) : null}

      {showBackgroundRefresh ? (
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/80">
          <Loader2 className="h-3 w-3 animate-spin" />
          Refreshing insights…
        </div>
      ) : null}
    </div>
  )
}
