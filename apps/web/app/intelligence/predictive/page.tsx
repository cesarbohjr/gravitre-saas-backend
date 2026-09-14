"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { PredictionsStage } from "@/components/intelligence/pages/predictions-stage"
import { useAuth } from "@/lib/auth-context"
import { ApiError } from "@/lib/fetcher"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { ArrowsClockwise } from "@phosphor-icons/react"

const copy = SURFACE_COPY.pages.predictive

export default function PredictiveOpsPage() {
  const { user } = useAuth()
  const {
    data: pageContext,
    loadState,
    generatedAt,
    isValidating,
    mutate,
    error,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens: "predicts",
    swrKeySuffix: "predictions",
  })
  const suggestedQuestions = pageContext?.suggestedQuestions ?? []

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view business predictions." />
      </AppShell>
    )
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load predictions."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load predictions" description={message} onRetry={() => mutate()} />
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
          activeTab="predictions"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
          <PredictionsStage
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
