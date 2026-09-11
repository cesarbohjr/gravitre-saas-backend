"use client"

/**
 * Intelligence redesign Phase 1 (2026-09-11) — Performance is a new,
 * first-class Intelligence destination for real, measured business outcomes
 * (hours automated, ROI, business-impact score, revenue-risk signals).
 *
 * This composes existing, real components rather than inventing a new data
 * model, per the redesign brief: `BusinessImpactCard` and `AgentRoiPanel`
 * already pull real org data and already render honest "—" / empty states
 * when measurement isn't available. Phase 1 scope is making Performance a
 * visible, always-reachable primary destination with real content wired in;
 * a fuller Phase 7 pass (dedicated KNOWS/LEARNS/PREDICTS/ACTS/IMPROVES
 * framing) is tracked separately and does not block this from being real.
 */
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitreMetric, GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { StatsSkeleton } from "@/components/gravitre/loading-state"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { formatPercent, readNumber } from "@/lib/intelligence/helpers"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import { ESTIMATED_CONFIDENCE_LABEL } from "@/lib/outcome-labels"
import { BusinessImpactCard } from "../../admin/intelligence/_components/business-impact-card"
import { AgentRoiPanel } from "@/components/enterprise/agent-roi-panel"

const copy = {
  title: "Performance",
  description:
    "Measured business outcomes: hours automated, ROI, business-impact score, and revenue-risk signals — no fabricated numbers, honest dashes when a metric isn't measurable yet.",
}

export default function IntelligencePerformancePage() {
  const { user } = useAuth()
  const { data: outcomes, error, mutate, isLoading } = useSWR(
    user ? ["intelligence/performance/outcomes", 30] : null,
    () => intelligenceApi.outcomes({ periodDays: 30 }),
    { revalidateOnFocus: false },
  )
  const { data: trust } = useSWR(user ? "intelligence/performance/trust-summary" : null, () =>
    intelligenceApi.trustSummary({ periodDays: 30 }),
  )

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view performance." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load performance"
          description={error instanceof ApiError ? error.message : "Try again in a moment."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const summary = (outcomes?.summary as Record<string, unknown> | undefined) ?? {}
  const byEvent = (outcomes?.by_event_type as Record<string, number> | undefined) ?? {}
  const totalEvents = readNumber(summary.total_events, 0)
  const avgConfidence = trust?.avg_confidence as number | null | undefined
  const trustRecord = trust as Record<string, unknown> | undefined
  const confidenceIsEstimate = Boolean(
    trustRecord?.confidence_is_estimate ?? trustRecord?.confidenceIsEstimate,
  )

  return (
    <AppShell title={copy.title}>
      <div className="space-y-6 p-4 md:p-6">
        <GravitrePageHeader
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
        />

        <IntelligenceHubTabs active="performance" />

        {isLoading && !outcomes ? (
          <StatsSkeleton count={4} />
        ) : totalEvents === 0 ? (
          <EmptyState
            variant="ai"
            title="No measured outcomes yet"
            description="Business-outcome events appear here once agents finish work with measurable results over the last 30 days."
          />
        ) : (
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] lg:grid-cols-4">
            <GravitreMetric
              label="Outcomes (30d)"
              value={totalEvents}
              hint="Business outcomes measured"
              icon={<NucleoIntelligence className="h-4 w-4" />}
            />
            <GravitreMetric
              label={confidenceIsEstimate ? ESTIMATED_CONFIDENCE_LABEL : "Avg confidence"}
              value={
                avgConfidence != null ? (
                  <span className="inline-flex flex-col gap-1">
                    <span>{formatPercent(avgConfidence)}</span>
                    <ConfidenceBadge
                      score={avgConfidence}
                      isEstimate={confidenceIsEstimate}
                      showScore={false}
                      className="text-[10px] normal-case tracking-normal"
                    />
                  </span>
                ) : (
                  "—"
                )
              }
              hint={confidenceIsEstimate ? "Estimate" : "Trust period"}
              warning={confidenceIsEstimate}
            />
            <GravitreMetric
              label="Recommendations created"
              value={readNumber(byEvent.recommendation_created, 0)}
              hint="Last 30 days"
            />
            <GravitreMetric
              label="Recommendations rejected"
              value={readNumber(byEvent.recommendation_rejected, 0)}
              hint="Last 30 days"
              warning={readNumber(byEvent.recommendation_rejected, 0) > 0}
            />
          </section>
        )}

        <div>
          <h2 className="mb-3 text-sm font-semibold text-foreground">Business-impact score &amp; revenue risk</h2>
          <BusinessImpactCard />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-foreground">Agent ROI — hours automated &amp; estimated value</h2>
          <AgentRoiPanel defaultPeriodDays={30} />
        </div>
      </div>
    </AppShell>
  )
}
