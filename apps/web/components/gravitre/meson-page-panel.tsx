"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AnimatePresence, motion } from "framer-motion"
import { Blocks, Lightbulb, Loader2, TrendingUp } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { mesonApi, type MesonInsight, type MesonSuggestion } from "@/lib/api"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

export type MesonPageId = "ai-chat" | "model-registry" | "model-detail" | "agent-detail" | string

const BANNER_ROTATE_MS = 7_000

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

type BannerSlide = "suggestions" | "insights"

function MesonLogo({ compact }: { compact?: boolean }) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-sm shadow-violet-500/25",
        compact ? "h-8 w-8" : "h-9 w-9",
      )}
    >
      <Blocks className={cn("text-white", compact ? "h-3.5 w-3.5" : "h-4 w-4")} />
    </div>
  )
}

function MesonBannerBody({
  slide,
  suggestion,
  insight,
  extraSuggestions,
  extraInsights,
  compact,
  onSuggestionClick,
}: {
  slide: BannerSlide
  suggestion?: MesonSuggestion
  insight?: MesonInsight
  extraSuggestions: number
  extraInsights: number
  compact?: boolean
  onSuggestionClick?: (suggestion: MesonSuggestion) => void
}) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      {slide === "suggestions" && suggestion ? (
        <motion.div
          key={`suggestion-${suggestion.id}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.22 }}
          className="min-h-[4.5rem]"
        >
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-600 dark:text-violet-300">
              <Lightbulb className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              {onSuggestionClick ? (
                <button
                  type="button"
                  onClick={() => onSuggestionClick(suggestion)}
                  className="text-left text-sm font-medium leading-snug text-foreground hover:text-violet-700 dark:hover:text-violet-200"
                >
                  {suggestion.label}
                </button>
              ) : (
                <p className="text-sm font-medium leading-snug text-foreground">{suggestion.label}</p>
              )}
              {suggestion.reason ? (
                <p className={cn("mt-1 line-clamp-2 text-muted-foreground", compact ? "text-[11px]" : "text-xs")}>
                  {suggestion.reason}
                </p>
              ) : null}
              {extraSuggestions > 0 ? (
                <p className="mt-1.5 text-[10px] font-medium text-violet-600/80 dark:text-violet-300/80">
                  +{extraSuggestions} more suggestion{extraSuggestions === 1 ? "" : "s"}
                </p>
              ) : null}
            </div>
          </div>
        </motion.div>
      ) : null}

      {slide === "insights" && insight ? (
        <motion.div
          key={`insight-${insight.id}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.22 }}
          className="min-h-[4.5rem]"
        >
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-600 dark:text-violet-300">
              <TrendingUp className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium leading-snug text-foreground">{insight.title}</p>
              <p className={cn("mt-1 line-clamp-3 text-muted-foreground", compact ? "text-[11px]" : "text-xs")}>
                {insight.summary}
              </p>
              {extraInsights > 0 ? (
                <p className="mt-1.5 text-[10px] font-medium text-violet-600/80 dark:text-violet-300/80">
                  +{extraInsights} more insight{extraInsights === 1 ? "" : "s"}
                </p>
              ) : null}
            </div>
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  )
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

  const hasSuggestions = suggestions.length > 0
  const hasInsights = insights.length > 0
  const shouldAlternate = hasSuggestions && hasInsights

  const defaultSlide: BannerSlide = hasSuggestions ? "suggestions" : "insights"
  const [activeSlide, setActiveSlide] = useState<BannerSlide>(defaultSlide)

  useEffect(() => {
    setActiveSlide(hasSuggestions ? "suggestions" : "insights")
  }, [hasSuggestions, hasInsights])

  useEffect(() => {
    if (!shouldAlternate) return
    const timer = window.setInterval(() => {
      setActiveSlide((current) => (current === "suggestions" ? "insights" : "suggestions"))
    }, BANNER_ROTATE_MS)
    return () => window.clearInterval(timer)
  }, [shouldAlternate])

  const slideLabel = useMemo(() => {
    if (activeSlide === "suggestions") return "Meson suggests"
    return "Meson insights"
  }, [activeSlide])

  const showInitialLoad =
    isLoading && !data && streamedInsights.length === 0 && streamedSuggestions.length === 0
  const showBackgroundRefresh = isValidating && !showInitialLoad && Boolean(data)
  const showEmpty = !showInitialLoad && !error && !hasSuggestions && !hasInsights

  return (
    <div className={cn(className)}>
      <div
        className={cn(
          "relative overflow-hidden rounded-xl border border-violet-500/25 bg-gradient-to-br from-violet-500/12 via-violet-500/6 to-purple-500/4 shadow-sm shadow-violet-500/10",
          compact ? "p-3.5" : "p-4",
        )}
      >
        <div
          aria-hidden
          className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-violet-500/10 blur-2xl"
        />

        <div className="relative flex items-start gap-3">
          <MesonLogo compact={compact} />
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-foreground">Meson</p>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-violet-600 dark:text-violet-300">
                  {slideLabel}
                </p>
              </div>
              {advisorBrief?.confidence != null ? (
                <span className="shrink-0 rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-0.5 text-[10px] font-medium text-violet-700 dark:text-violet-200">
                  {Math.round(advisorBrief.confidence * 100)}%
                </span>
              ) : null}
            </div>

            {showInitialLoad ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-3/4 bg-violet-500/10" />
                <Skeleton className="h-3 w-full bg-violet-500/10" />
                <Skeleton className="h-3 w-5/6 bg-violet-500/10" />
              </div>
            ) : showEmpty ? (
              <p className="text-xs leading-relaxed text-muted-foreground">
                {error
                  ? "Insights unavailable right now."
                  : "Monitoring your org — suggestions and insights appear as Meson learns."}
              </p>
            ) : (
              <MesonBannerBody
                slide={activeSlide}
                suggestion={suggestions[0]}
                insight={insights[0]}
                extraSuggestions={Math.max(0, suggestions.length - 1)}
                extraInsights={Math.max(0, insights.length - 1)}
                compact={compact}
                onSuggestionClick={onSuggestionClick}
              />
            )}
          </div>
        </div>

        {shouldAlternate && !showInitialLoad && !showEmpty ? (
          <div className="relative mt-3 flex items-center justify-center gap-1.5">
            {(["suggestions", "insights"] as const).map((slide) => (
              <button
                key={slide}
                type="button"
                aria-label={slide === "suggestions" ? "Show Meson suggestions" : "Show Meson insights"}
                aria-pressed={activeSlide === slide}
                onClick={() => setActiveSlide(slide)}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  activeSlide === slide ? "w-4 bg-violet-500" : "w-1.5 bg-violet-500/30 hover:bg-violet-500/50",
                )}
              />
            ))}
          </div>
        ) : null}

        {showBackgroundRefresh ? (
          <div className="relative mt-2 flex items-center gap-1.5 text-[10px] text-violet-700/70 dark:text-violet-200/70">
            <Loader2 className="h-3 w-3 animate-spin" />
            Refreshing…
          </div>
        ) : null}
      </div>

      {!compact ? (
        <p className="mt-2 text-[10px] text-muted-foreground">
          Advisory only — review before acting.{" "}
          <Link href="/intelligence" className="text-violet-600 underline-offset-4 hover:underline dark:text-violet-300">
            Intelligence Center
          </Link>
        </p>
      ) : null}
    </div>
  )
}
