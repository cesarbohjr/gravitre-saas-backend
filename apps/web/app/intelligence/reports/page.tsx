"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { ReportsStage } from "@/components/intelligence/pages/reports-stage"
import { useAuth } from "@/lib/auth-context"
import { ApiError } from "@/lib/fetcher"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { ArrowsClockwise } from "@phosphor-icons/react"

const copy = SURFACE_COPY.pages.reports

export default function IntelligenceReportsPage() {
  const { user } = useAuth()
  const orgId = typeof window !== "undefined" ? getSelectedOrgFromStorage()?.id : undefined
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
    swrKeySuffix: "reports",
  })

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view reports." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load reports"
          description={error instanceof ApiError ? error.message : "Please try again."}
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
          activeTab="reports"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutate()}
        >
          <ReportsStage
            pageContext={pageContext}
            loadState={loadState}
            enabled={Boolean(user)}
            orgId={orgId}
            suggestedQuestions={pageContext?.suggestedQuestions}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
