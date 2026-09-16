"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { PerformanceStage } from "@/components/intelligence/pages/performance-stage"
import { useAuth } from "@/lib/auth-context"
import { ApiError } from "@/lib/fetcher"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { ArrowsClockwise } from "@phosphor-icons/react"

const copy = {
  title: "Performance",
  description:
    "Is Gravitre making the business better? Outcome attribution, contribution, and evidence — not a telemetry dashboard.",
}

export default function IntelligencePerformancePage() {
  const { user } = useAuth()
  const {
    data: pageContext,
    error,
    loadState,
    generatedAt,
    isValidating,
    mutate,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens: "improves",
    windowHours: 24 * 30,
    swrKeySuffix: "performance",
  })
  const suggestedQuestions = pageContext?.suggestedQuestions ?? []

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
          activeTab="performance"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
          <PerformanceStage
            pageContext={pageContext}
            loadState={loadState}
            enabled={Boolean(user)}
            suggestedQuestions={suggestedQuestions}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
