"use client"

import { INTEL } from "@/components/intelligence/shell/intel-ui"
import { cn } from "@/lib/utils"
import { useCallback, useState } from "react"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { PerformanceStage } from "@/components/intelligence/pages/performance-stage"
import {
  IMPACT_PERIODS,
  impactCsv,
  type ImpactPeriod,
} from "@/components/intelligence/impact/impact-model"
import { useAuth } from "@/lib/auth-context"
import { connectorsApi, enterpriseApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { INTELLIGENCE_PAGE_FRAME } from "@/lib/design-system"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

const copy = {
  title: "Impact",
  eyebrow: "Understand / Impact",
  description:
    "What your agents did, what it cost and what it was worth. A dash means Gravitre has no evidence yet, never zero.",
}

const PERIOD_OPTIONS = IMPACT_PERIODS.map((days) => ({ id: String(days) as `${ImpactPeriod}`, label: `${days} days` }))

function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function IntelligencePerformancePage() {
  const { user } = useAuth()
  const enabled = Boolean(user)
  const [period, setPeriod] = useState<ImpactPeriod>(30)

  const {
    data: pageContext,
    loadState,
    generatedAt,
    isValidating,
    mutate,
  } = useIntelligenceSnapshot({
    enabled,
    activeLens: "improves",
    windowHours: 24 * period,
    swrKeySuffix: "performance",
  })

  const {
    data: roi,
    error: roiError,
    isLoading: roiLoading,
    mutate: mutateRoi,
  } = useSWR(
    enabled ? ["intelligence/performance/agent-roi", period] : null,
    () => enterpriseApi.getAgentRoi({ periodDays: period }),
    { revalidateOnFocus: false, keepPreviousData: true },
  )

  const { data: connectorsPayload, isLoading: connectorsLoading } = useSWR(
    enabled ? "/api/connectors" : null,
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )

  const refresh = useCallback(() => {
    mutate()
    void mutateRoi()
  }, [mutate, mutateRoi])

  const exportCsv = useCallback(() => {
    if (!roi) return
    const day = new Date().toISOString().slice(0, 10)
    downloadCsv(`gravitre-impact-${period}d-${day}.csv`, impactCsv({ report: roi, period }))
  }, [roi, period])

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view impact." />
      </AppShell>
    )
  }

  // Data is for the period shown only once the matching report has arrived.
  const roiForPeriod = roi && roi.periodDays === period ? roi : undefined

  return (
    <AppShell title={copy.title}>
      <div className={INTELLIGENCE_PAGE_FRAME} data-composition="understand">
        <GravitrePageHeader
          eyebrow={copy.eyebrow}
          titleScale="display"
          title={copy.title}
          description={copy.description}
          icon={<NucleoIntelligence className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <div role="radiogroup" aria-label="Period" className={INTEL.segment}>
                {PERIOD_OPTIONS.map((option) => {
                  const on = option.id === String(period)
                  return (
                    <button
                      key={option.id}
                      type="button"
                      role="radio"
                      aria-checked={on}
                      onClick={() => setPeriod(Number(option.id) as ImpactPeriod)}
                      className={cn(INTEL.segmentItem, on && INTEL.segmentItemOn)}
                    >
                      {option.label}
                    </button>
                  )
                })}
              </div>
              <button
                type="button"
                className={INTEL.outlineButton}
                onClick={exportCsv}
                disabled={!roiForPeriod}
                title={roiForPeriod ? `Download the last ${period} days as CSV` : "Available once this period has loaded"}
              >
                Export
              </button>
            </div>
          }
        />

        <IntelligenceShell
          activeTab="performance"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={refresh}
        >
          {roiError && !roi ? (
            <ErrorState
              title="Unable to load spend and agent results"
              description={roiError instanceof ApiError ? roiError.message : "Try again in a moment."}
              onRetry={refresh}
            />
          ) : null}
          <PerformanceStage
            pageContext={pageContext}
            loadState={loadState}
            period={period}
            roi={roiForPeriod}
            roiLoading={roiLoading || (!roiForPeriod && !roiError)}
            connectors={connectorsPayload?.connectors}
            connectorsLoading={connectorsLoading}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
