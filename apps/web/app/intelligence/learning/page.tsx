"use client"

import useSWR from "swr"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import { LearningSurfacesCallout } from "@/components/gravitre/learning-surfaces-callout"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { readNumber } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { BusinessImpactCard } from "../../admin/intelligence/_components/business-impact-card"
import { APP_ROUTES } from "@/lib/app-routes"
import { ArrowsClockwise } from "@phosphor-icons/react"

type LearningInsightRow = {
  id?: string
  businessStatement?: string
  learnedAt?: string | null
  confidence?: string | null
  learnedFrom?: string[]
}

export default function IntelligenceLearningPage() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.learning

  const { data: pageContext, error, isLoading, isValidating, mutate } = useSWR(
    user ? ["intelligence/learning/page-context"] : null,
    () => intelligenceApi.pageContext({ windowHours: 24, activeLens: "learns" }),
    { revalidateOnFocus: false },
  )

  const learnings = (pageContext?.snapshot.learnings ?? []) as LearningInsightRow[]
  const learningMetrics =
    pageContext?.metrics.learning ?? pageContext?.snapshot.metrics.learning ?? {}
  const recentCount = readNumber(learningMetrics.recentLearnings, learnings.length)
  const relationshipsLearned = readNumber(learningMetrics.relationshipsLearned, 0)
  const hasNoBusinessLearning = pageContext?.qualityFlags?.includes("NO_BUSINESS_LEARNING_YET")

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view business learning insights." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load learning insights."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load learning" description={message} onRetry={() => mutate()} />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        <LearningSurfacesCallout current="org-learning" />

        <GravitrePageHeader
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" onClick={() => mutate()} disabled={isValidating}>
              <ArrowsClockwise
                className={`mr-2 h-4 w-4 ${isValidating ? "animate-spin" : ""}`}
                weight="bold"
                aria-hidden
              />
              Refresh
            </Button>
          }
        />

        <IntelligenceHubTabs active="learning" />

        <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-3">
          <GravitreMetric
            label="Recent learnings"
            value={isLoading ? "…" : recentCount}
            hint="Validated business insights"
          />
          <GravitreMetric
            label="Relationships known"
            value={isLoading ? "…" : relationshipsLearned}
            hint="Knowledge graph connections"
          />
          <GravitreMetric
            label="Memory promotions"
            value={isLoading ? "…" : readNumber(learningMetrics.modelsTracked, 0)}
            hint="Sources feeding learning"
          />
        </section>

        <BusinessImpactCard />

        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">What Gravitre learned</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Business understanding from outcomes, memory, and evidence — not platform latency or model
              readiness scores.
            </p>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading business learning insights…</p>
          ) : learnings.length === 0 || hasNoBusinessLearning ? (
            <EmptyState
              variant="ai"
              title="No validated business learning yet"
              description="Insights appear here when Gravitre records durable business understanding from real work — not deployment health or training readiness."
              action={{
                label: "Open Training",
                onClick: () => {
                  window.location.href = APP_ROUTES.training
                },
                variant: "outline",
              }}
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {learnings.map((row) => (
                <Card key={row.id ?? row.businessStatement}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base font-medium leading-snug">
                      {row.businessStatement ?? "Learning insight"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1 text-sm text-muted-foreground">
                    {row.learnedAt ? <p>Learned {new Date(row.learnedAt).toLocaleDateString()}</p> : null}
                    {row.learnedFrom?.length ? (
                      <p>From: {row.learnedFrom.join(", ")}</p>
                    ) : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </section>

        <p className="text-xs text-muted-foreground">
          Platform telemetry (TTFT, cache hit rate, cognitive turn traces) lives in{" "}
          <Link href={APP_ROUTES.adminIntelligence} className="font-medium text-[color:var(--g-brand)] hover:underline">
            Platform intelligence (admin)
          </Link>
          .
        </p>
      </div>
    </AppShell>
  )
}
