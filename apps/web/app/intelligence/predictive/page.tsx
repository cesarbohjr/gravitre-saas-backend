"use client"

import { useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { DataFreshness } from "@/components/gravitre/data-freshness"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { PredictionsStage } from "@/components/intelligence/pages/predictions-stage"
import type { FailureAlertWithEvidence } from "@/components/intelligence/forecasts/forecast-model"
import { workflowsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { PAGE_FRAME } from "@/lib/design-system"
import { ApiError } from "@/lib/fetcher"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { ArrowsClockwise } from "@phosphor-icons/react"

const copy = SURFACE_COPY.pages.predictive

/** Same SWR key as the Activity › Failures panel so both share one cache entry. */
const FAILURE_ALERTS_KEY = ["workflow-failure-predictions", "open"] as const

export default function PredictiveOpsPage() {
  const { user } = useAuth()
  const [scanning, setScanning] = useState(false)
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
  const alerts = useSWR(
    user ? FAILURE_ALERTS_KEY : null,
    () => workflowsApi.listFailurePredictions({ status: "open" }),
    { revalidateOnFocus: false },
  )

  const refreshing = isValidating || alerts.isValidating
  const refresh = () => {
    mutate()
    void alerts.mutate()
  }

  const scanWorkflows = async () => {
    setScanning(true)
    try {
      const result = await workflowsApi.scanAllFailurePredictions()
      await alerts.mutate()
      toast.success(
        result.alertCount > 0
          ? `Checked ${result.scannedCount} workflow${result.scannedCount === 1 ? "" : "s"}. ${result.alertCount} likely to fail.`
          : `Checked ${result.scannedCount} workflow${result.scannedCount === 1 ? "" : "s"}. Nothing looks likely to fail.`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't check workflows.")
    } finally {
      setScanning(false)
    }
  }

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view forecasts." />
      </AppShell>
    )
  }

  if (error && alerts.error) {
    const message = error instanceof ApiError ? error.message : "Failed to load forecasts."
    return (
      <AppShell title={copy.title}>
        <ErrorState title="Unable to load forecasts" description={message} onRetry={refresh} />
      </AppShell>
    )
  }

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME}>
        <GravitrePageHeader
          eyebrow="Understand / Forecasts"
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex items-center gap-3">
              <DataFreshness updatedAt={generatedAt} isRefreshing={refreshing} />
              <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing}>
                <ArrowsClockwise
                  className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
                  weight="bold"
                  aria-hidden
                />
                Refresh
              </Button>
            </div>
          }
        />

        <IntelligenceShell
          activeTab="predictions"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          showFreshness={false}
        >
          {error ? (
            <p role="status" className="mb-4 text-sm text-muted-foreground">
              Business forecasts couldn&apos;t load, so only workflow forecasts are shown.
            </p>
          ) : null}
          {alerts.error ? (
            <p role="status" className="mb-4 text-sm text-muted-foreground">
              Workflow forecasts couldn&apos;t load, so only business forecasts are shown.
            </p>
          ) : null}
          <PredictionsStage
            pageContext={pageContext}
            loadState={loadState}
            failureAlerts={alerts.data?.alerts as FailureAlertWithEvidence[] | undefined}
            failureAlertsLoaded={Boolean(alerts.data) || Boolean(alerts.error)}
            onAlertsChanged={() => void alerts.mutate()}
            onScanWorkflows={() => void scanWorkflows()}
            scanning={scanning}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
