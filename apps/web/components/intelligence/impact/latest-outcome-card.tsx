"use client"

import Link from "next/link"
import type { OutcomeAttributionPath } from "@/lib/api"
import { outcomeProgress } from "@/components/intelligence/impact/impact-model"
import { outcomeHeadline } from "@/lib/intelligence/performance-display"
import { APP_ROUTES } from "@/lib/app-routes"
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
      className="rounded-[var(--np-radius-lg)] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-5"
    >
      <p className={cn(TYPE.eyebrow, "uppercase tracking-[0.08em]")}>Latest outcome</p>
      <h2 id="impact-outcome-heading" className={cn(TYPE.cardTitle, "mt-2 text-pretty")}>
        {loading ? "Loading outcome…" : headline ?? "No outcome recorded in this period"}
      </h2>

      {progress ? (
        <>
          <div
            className="mt-4 flex gap-1"
            role="img"
            aria-label={`${progress.present} of ${progress.total} steps have evidence`}
          >
            {progress.segments.map((present, i) => (
              <span
                key={i}
                className={cn(
                  "h-1.5 flex-1 rounded-full",
                  present ? "bg-[color:var(--g-brand)]" : "bg-[color:var(--g-surface-3)]",
                )}
              />
            ))}
          </div>
          <p className={cn(TYPE.meta, "mt-3")}>{progress.summary}</p>
        </>
      ) : !loading ? (
        <p className={cn(TYPE.meta, "mt-2")}>
          The trail fills in once a signal, an agent action and a result are linked.
        </p>
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
