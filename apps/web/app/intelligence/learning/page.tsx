"use client"

import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"
import { LearningInsightCard } from "@/components/intelligence/learning-insight-card"
import { LearningHubLinks } from "@/components/intelligence/learning-hub-links"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { ApiError } from "@/lib/fetcher"
import { readNumber } from "@/lib/intelligence/helpers"
import { formatLearningInsights } from "@/lib/intelligence/learning-insight-display"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { BusinessImpactCard } from "../../admin/intelligence/_components/business-impact-card"
import { APP_ROUTES, LEGACY_APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowsClockwise } from "@phosphor-icons/react"

export default function IntelligenceLearningPage() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.learning

  const {
    data: pageContext,
    error,
    loadState,
    generatedAt,
    isValidating,
    mutate,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens: "learns",
    swrKeySuffix: "learning",
  })
  const metricsReady = isSnapshotMetricsReady(loadState)
  const isLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"

  const insights = formatLearningInsights(
    pageContext?.snapshot.learnings as Record<string, unknown>[] | undefined,
  )
  const learningMetrics =
    pageContext?.metrics.learning ?? pageContext?.snapshot.metrics.learning ?? {}
  const outcomeMetrics =
    pageContext?.metrics.outcomes ?? pageContext?.snapshot.metrics.outcomes ?? {}
  const recentCount = metricsReady
    ? readNumber(learningMetrics.recentLearnings, insights.length)
    : null
  const relationshipsLearned = metricsReady
    ? readNumber(learningMetrics.relationshipsLearned, 0)
    : null
  const measuredOutcomes = metricsReady
    ? readNumber(outcomeMetrics.measuredOutcomes, 0)
    : null
  const modelsTracked = metricsReady
    ? readNumber(learningMetrics.modelsTracked, 0)
    : null
  const hasNoBusinessLearning = pageContext?.qualityFlags?.includes("NO_BUSINESS_LEARNING_YET")
  const suggestedQuestions = pageContext?.suggestedQuestions ?? []

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
      <div className="mx-auto max-w-6xl space-y-8 p-4 sm:p-6">
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

        <IntelligenceShell
          activeTab="learning"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
        <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
          <GravitreMetric
            label="Recent learnings"
            value={recentCount ?? "—"}
            hint={isLoading ? "Loading intelligence…" : "Validated business insights"}
          />
          <GravitreMetric
            label="Relationships known"
            value={relationshipsLearned ?? "—"}
            hint={isLoading ? "Loading intelligence…" : "Knowledge graph connections"}
          />
          <GravitreMetric
            label="Measured outcomes"
            value={measuredOutcomes ?? "—"}
            hint={isLoading ? "Loading intelligence…" : "Window attribution"}
          />
          <GravitreMetric
            label="Models tracked"
            value={modelsTracked ?? "—"}
            hint={isLoading ? "Loading intelligence…" : "Registry scope — not learning claims"}
          />
        </section>

        <BusinessImpactCard />

        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-foreground">What Gravitre learned</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Business understanding from outcomes, memory promotion, and evidence — not platform
              latency or model readiness scores.
            </p>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading business learning insights…</p>
          ) : insights.length === 0 || hasNoBusinessLearning ? (
            <EmptyState
              variant="ai"
              title="No validated business learning yet"
              description="Insights appear here when Gravitre records durable business understanding from real work — not deployment health or training readiness."
              action={{
                label: "Open memory",
                onClick: () => {
                  window.location.href = APP_ROUTES.intelligenceMemory
                },
                variant: "outline",
              }}
            />
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {insights.map((insight) => (
                <LearningInsightCard key={insight.id} insight={insight} />
              ))}
            </div>
          )}
        </section>

        {suggestedQuestions.length > 0 ? (
          <section className="space-y-3">
            <p className={TYPE.eyebrow}>Ask Gravitre</p>
            <div className="flex flex-wrap gap-2">
              {suggestedQuestions.slice(0, 4).map((question) => (
                <Link
                  key={question}
                  href={`${APP_ROUTES.gravitreAi}?q=${encodeURIComponent(question)}`}
                  className="rounded-full border border-divide bg-[color:var(--g-surface-2)] px-3 py-1.5 text-xs font-medium hover:border-[color:var(--g-brand-border)]"
                >
                  {question}
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        <LearningHubLinks />

        <p className={cn(TYPE.meta, "text-pretty")}>
          Platform telemetry (TTFT, cache hit rate, cognitive turn traces) lives in{" "}
          <Link
            href={LEGACY_APP_ROUTES.adminIntelligence}
            className="font-medium text-[color:var(--g-brand)] hover:underline"
          >
            Platform intelligence (admin)
          </Link>
          .
        </p>
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
