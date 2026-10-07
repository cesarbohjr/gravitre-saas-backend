"use client"

import Link from "next/link"
import type { OutcomeAttributionPath } from "@/lib/api"
import { OUTCOME_PATH_STEP_COUNT, outcomeProgress } from "@/components/intelligence/impact/impact-model"
import { outcomeHeadline } from "@/lib/intelligence/performance-display"
import { APP_ROUTES } from "@/lib/app-routes"
import { IMPACT_MICRO_LABEL } from "@/components/intelligence/impact/certainty"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export function LatestOutcomeCard({
  path,
  loading,
}: {
  path: OutcomeAttributionPath | null
  loading: boolean
}) {
  const progress = outcomeProgress(path)
  const headline = outcomeHeadline(path)

  return (
    <section
      aria-labelledby="impact-outcome-heading"
      className="rounded-[18px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-5"
    >
      <p className={IMPACT_MICRO_LABEL}>Latest outcome</p>
      <h2 id="impact-outcome-heading" className={cn(TYPE.cardTitle, "mt-3 text-[15px] leading-[1.4] text-pretty")}>
        {loading ? "Loading outcome…" : headline ?? "No outcome recorded in this period"}
      </h2>

      {!loading ? (
        <>
          <div
            className="mt-3 flex gap-1"
            role="img"
            aria-label={
              progress
                ? `${progress.present} of ${progress.total} steps have evidence`
                : "No steps have evidence yet"
            }
          >
            {(progress?.segments ?? Array<boolean>(OUTCOME_PATH_STEP_COUNT).fill(false)).map((present, i) => (
              <span
                key={i}
                className={cn(
                  "h-1.5 flex-1 rounded-full",
                  present ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-surface-3)]",
                )}
              />
            ))}
          </div>
          <p className="mt-3 text-[12.5px] text-[color:var(--g-text-secondary)]">
            {progress
              ? progress.summary
              : "No steps have evidence yet. The trail fills in once a signal, an agent action and a result are linked."}
          </p>
        </>
      ) : null}

      <Link
        href={APP_ROUTES.intelligenceReports}
        className="mt-3 inline-block text-[13px] font-medium text-[color:var(--g-brand-active)] underline underline-offset-2 hover:text-[color:var(--g-brand-hover)] dark:text-[color:var(--g-brand)]"
      >
        Open the evidence trail →
      </Link>
    </section>
  )
}
