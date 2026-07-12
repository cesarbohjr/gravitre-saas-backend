"use client"

import Link from "next/link"
import useSWR from "swr"
import { ArrowRight, X } from "@phosphor-icons/react"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"

type HeuristicCard = {
  id: string
  kind: string
  title: string
  reason: string
  confidence: number
  priority: number
  advisoryOnly: boolean
  href: string
}

type HeuristicResponse = {
  advisoryOnly: boolean
  actionsTaken: unknown[]
  recommendations: HeuristicCard[]
  count: number
}

/**
 * STA-314 suggest-only cards.
 * Intentionally has no Execute / Apply / Install / Schedule handlers —
 * navigation links + dismiss only. Writes still go through chat confirm / execute_plan.
 */
export function HeuristicSuggestionCards() {
  const { user } = useAuth()
  const { data, error, isLoading, mutate } = useSWR<HeuristicResponse>(
    user ? "intelligence/recommendations/heuristics" : null,
    () => intelligenceApi.heuristicRecommendations() as Promise<HeuristicResponse>,
    { revalidateOnFocus: false },
  )

  const dismiss = async (cardId: string) => {
    await mutate(
      (current) =>
        current
          ? {
              ...current,
              recommendations: current.recommendations.filter((c) => c.id !== cardId),
              count: Math.max(0, (current.count || 0) - 1),
            }
          : current,
      { revalidate: false },
    )
    try {
      await intelligenceApi.dismissHeuristicRecommendation(cardId)
    } catch {
      mutate()
    }
  }

  if (!user || isLoading) return null
  if (error || !data?.recommendations?.length) return null

  return (
    <section className="space-y-3" data-testid="heuristic-suggestion-cards">
      <div>
        <h2 className="text-sm font-medium text-foreground">Suggested next steps</h2>
        <p className="text-xs text-muted-foreground">
          Advisory only — open a surface to act; nothing runs from these cards.
        </p>
      </div>
      <ul className="space-y-2">
        {data.recommendations.map((card) => (
          <li
            key={card.id}
            className="rounded-lg border border-border bg-card px-4 py-3"
            data-testid={`heuristic-card-${card.kind}`}
            data-advisory-only={card.advisoryOnly ? "true" : "false"}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <p className="text-sm font-medium text-foreground">{card.title}</p>
                <p className="text-xs text-muted-foreground">{card.reason}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {card.href ? (
                  <Link
                    href={card.href}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    data-testid="heuristic-card-nav"
                  >
                    Open
                    <ArrowRight className="h-3 w-3" />
                  </Link>
                ) : null}
                <button
                  type="button"
                  aria-label={`Dismiss ${card.title}`}
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  data-testid="heuristic-card-dismiss"
                  onClick={() => void dismiss(card.id)}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
