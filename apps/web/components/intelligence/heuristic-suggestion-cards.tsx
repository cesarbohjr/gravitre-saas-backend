"use client"

import Link from "next/link"
import useSWR from "swr"
import { ArrowRight } from "@phosphor-icons/react"
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
 * navigation links only. Writes still go through chat confirm / execute_plan.
 */
export function HeuristicSuggestionCards() {
  const { user } = useAuth()
  const { data, error, isLoading } = useSWR<HeuristicResponse>(
    user ? "intelligence/recommendations/heuristics" : null,
    () => intelligenceApi.heuristicRecommendations() as Promise<HeuristicResponse>,
    { revalidateOnFocus: false },
  )

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
              {card.href ? (
                <Link
                  href={card.href}
                  className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
                  data-testid="heuristic-card-nav"
                >
                  Open
                  <ArrowRight className="h-3 w-3" />
                </Link>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
