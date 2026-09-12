"use client"

/**
 * Intelligence redesign, brief-Phase 3 (2026-09-11) — Overview Layer 3:
 * "Ask Gravitre." Present but deliberately not dominant — a compact entry
 * point into the same /ai surface used everywhere else, with real suggested
 * questions from the daily-briefing endpoint (never a scripted fake list).
 * Falls back to the brief's own example questions only as link *labels*,
 * not as invented answers or data.
 */

import Link from "next/link"
import useSWR from "swr"
import { assistantApi } from "@/lib/api"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { ArrowRight } from "@phosphor-icons/react"

const FALLBACK_QUESTIONS = ["What changed today?", "What needs attention?", "What have you learned?"]

export function useAskGravitreSuggestions(enabled: boolean) {
  return useSWR(
    enabled ? "intelligence/overview/daily-briefing" : null,
    () => assistantApi.dailyBriefing(),
    { revalidateOnFocus: false },
  )
}

export function AskGravitreEntry({
  suggestions,
  className,
}: {
  suggestions: string[] | null | undefined
  className?: string
}) {
  const questions = suggestions?.length ? suggestions.slice(0, 3) : FALLBACK_QUESTIONS
  const usingFallback = !suggestions?.length

  return (
    <section
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="ask-gravitre-heading"
      data-ask-gravitre-entry=""
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-intelligence-surface)] text-[color:var(--g-intelligence)]">
          <NucleoIntelligence className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className={TYPE.eyebrow}>Layer 3</p>
          <h2 id="ask-gravitre-heading" className={TYPE.sectionTitle}>
            Ask Gravitre
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1")}>
            One question away — the same assistant that answers everywhere else in the product.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {questions.map((question) => (
          <Link
            key={question}
            href={`/ai?prompt=${encodeURIComponent(question)}`}
            className="inline-flex items-center gap-1.5 rounded-full border border-divide bg-[color:var(--g-surface-2)] px-3 py-1.5 text-xs font-medium text-[color:var(--g-text-secondary)] transition-colors hover:border-[color:var(--g-brand-border)] hover:bg-[color:var(--g-brand-surface)] hover:text-[color:var(--g-brand)]"
          >
            {question}
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
        ))}
      </div>

      {usingFallback ? (
        <p className={cn(TYPE.meta, "mt-3")}>
          Showing example questions — a live daily briefing wasn&apos;t available for this org yet.
        </p>
      ) : null}

      <div className="mt-4">
        <Link
          href="/ai"
          className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          Open the full assistant
          <ArrowRight className="h-3 w-3" aria-hidden />
        </Link>
      </div>
    </section>
  )
}
