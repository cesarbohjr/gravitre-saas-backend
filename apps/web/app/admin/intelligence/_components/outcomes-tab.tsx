"use client"

import useSWR from "swr"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { intelligenceApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { ChartLineUp, CheckCircle, Hourglass, ArrowRight } from "@phosphor-icons/react"
import { NotYetPopulated, readNumber, SectionCard, TabStateGate } from "./shared"

type Summary = {
  agentId: string
  agentName?: string
  sampleSize: number
  minSampleSize: number
  sufficientData: boolean
  confidenceNote: string
  message?: string
  winRate?: number | null
}

function progressPct(sample: number, min: number): number {
  if (min <= 0) return 0
  return Math.max(0, Math.min(100, Math.round((sample / min) * 100)))
}

export function OutcomesTab({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? ["admin/intelligence/outcomes"] : null,
    () => intelligenceApi.outcomes(),
    { revalidateOnFocus: false },
  )

  const v8 = (data?.v8_outcome_attribution as Record<string, unknown> | undefined) ?? {}
  const summaries = ((v8.agentSummaries ?? data?.agentSummaries) ?? []) as Summary[]
  const ready = summaries.filter((item) => item.sufficientData)
  const building = summaries.filter((item) => !item.sufficientData)
  const closest = [...building].sort(
    (a, b) =>
      progressPct(readNumber(b.sampleSize), readNumber(b.minSampleSize)) -
      progressPct(readNumber(a.sampleSize), readNumber(a.minSampleSize)),
  )

  return (
    <TabStateGate isLoading={isLoading && !data} error={error} onRetry={() => mutate()}>
      <div className="space-y-6">
        <SectionCard
          title="Business outcomes"
          description="See which agents are tied to real results in your connected tools — deal movement, subscriptions, and campaign metrics. Patterns need enough samples before we show a win rate."
          icon={<ChartLineUp className="h-5 w-5" weight="duotone" aria-hidden />}
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border/70 bg-secondary/30 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Agents tracked</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{summaries.length}</p>
            </div>
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-emerald-800 dark:text-emerald-200">
                Ready to read
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-emerald-700 dark:text-emerald-300">
                {ready.length}
              </p>
            </div>
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3">
              <p className="text-xs font-medium uppercase tracking-wide text-amber-800 dark:text-amber-200">
                Still collecting
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-amber-700 dark:text-amber-300">
                {building.length}
              </p>
            </div>
          </div>

          <p className="mt-4 text-sm leading-relaxed text-muted-foreground text-pretty">
            Gravitre links agent work to observable connector results (for example HubSpot deal amounts or Stripe
            subscriptions). This shows correlation with enough history — not a guarantee that the agent caused the
            outcome.
          </p>
        </SectionCard>

        {summaries.length === 0 ? (
          <SectionCard title="Getting started" description="Outcomes appear after agents act on measurable work.">
            <NotYetPopulated>
              No outcome history yet. Run agents against HubSpot deals, Stripe customers, or marketing publishes — then
              refresh this page.
            </NotYetPopulated>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button asChild size="sm">
                <Link href={APP_ROUTES.gravitreAi}>
                  Open chat
                  <ArrowRight className="ml-1.5 h-4 w-4" weight="bold" aria-hidden />
                </Link>
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link href={APP_ROUTES.connectors}>Check connectors</Link>
              </Button>
            </div>
          </SectionCard>
        ) : (
          <>
            {ready.length > 0 ? (
              <SectionCard
                title="Agents with enough signal"
                description="Win rate is shown only after the minimum sample size is met."
                icon={<CheckCircle className="h-5 w-5" weight="duotone" aria-hidden />}
              >
                <div className="grid gap-3 sm:grid-cols-2">
                  {ready.map((summary) => (
                    <article
                      key={summary.agentId}
                      className="rounded-2xl border border-border/70 bg-background/70 p-4 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="font-medium text-foreground text-pretty">
                          {summary.agentName ?? "Agent"}
                        </h3>
                        <Badge className="bg-emerald-500/15 text-emerald-800 hover:bg-emerald-500/15 dark:text-emerald-200">
                          {(readNumber(summary.winRate) * 100).toFixed(0)}% win rate
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Based on {readNumber(summary.sampleSize)} measured results
                      </p>
                      {summary.confidenceNote ? (
                        <p className="mt-2 text-xs leading-relaxed text-muted-foreground text-pretty">
                          {summary.confidenceNote}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </SectionCard>
            ) : null}

            {building.length > 0 ? (
              <SectionCard
                title="Building a reliable sample"
                description="Each agent needs more measured results before a win rate is shown. Progress is toward that threshold — not a grade."
                icon={<Hourglass className="h-5 w-5" weight="duotone" aria-hidden />}
              >
                <ul className="space-y-3">
                  {closest.map((summary) => {
                    const sample = readNumber(summary.sampleSize)
                    const min = readNumber(summary.minSampleSize) || 15
                    const pct = progressPct(sample, min)
                    return (
                      <li
                        key={summary.agentId}
                        className="rounded-2xl border border-border/60 bg-secondary/20 px-4 py-3"
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="font-medium text-foreground">
                            {summary.agentName ?? summary.agentId}
                          </p>
                          <p className="text-sm tabular-nums text-muted-foreground">
                            {sample} of {min} results
                          </p>
                        </div>
                        <Progress value={pct} className="mt-2 h-2" aria-label={`${pct}% of sample threshold`} />
                        <p className="mt-1.5 text-xs text-muted-foreground">
                          {min - sample > 0
                            ? `${min - sample} more measured result${min - sample === 1 ? "" : "s"} to unlock a win rate`
                            : "Threshold met — refresh to see win rate"}
                        </p>
                      </li>
                    )
                  })}
                </ul>
              </SectionCard>
            ) : null}
          </>
        )}
      </div>
    </TabStateGate>
  )
}
