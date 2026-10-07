"use client"

import { Suspense, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import {
  usePublishGravitreAISelection,
  type GravitreAISelectedEntity,
} from "@/components/gravitre/ai-workspace-provider"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { IntelligenceBrain } from "@/components/intelligence/brain/intelligence-brain"
import type { OutcomeAttribution } from "@/components/intelligence/overview/flow-model"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { connectorsApi, intelligenceApi, memoryPromotionApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { ensureSelectedOrg } from "@/lib/org-context"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { PAGE_FRAME } from "@/lib/design-system"
import { SURFACE_COPY } from "@/lib/surface-copy"

function IntelligenceSectionRedirect() {
  const router = useRouter()
  const searchParams = useSearchParams()
  useEffect(() => {
    const section = searchParams.get("section")
    if (section === "operational-health") {
      router.replace("/metrics")
      return
    }
    if (section === "models") {
      router.replace(APP_ROUTES.models)
      return
    }
    if (section === "reports") {
      router.replace(APP_ROUTES.intelligenceReports)
      return
    }
    if (section === "learning") {
      router.replace(APP_ROUTES.learning)
      return
    }
    if (section === "memory") {
      router.replace(APP_ROUTES.intelligenceMemory)
      return
    }
    if (section === "predictive") {
      router.replace(APP_ROUTES.intelligencePredictive)
    }
  }, [router, searchParams])
  return null
}

function IntelligenceCenterInner() {
  const { user } = useAuth()
  const copy = SURFACE_COPY.insights
  const [orgReady, setOrgReady] = useState(false)
  const [selected, setSelected] = useState<GravitreAISelectedEntity | null>(null)
  usePublishGravitreAISelection(selected)

  useEffect(() => {
    if (!user) {
      setOrgReady(false)
      return
    }
    let cancelled = false
    void ensureSelectedOrg(true).then((orgId) => {
      if (!cancelled) setOrgReady(Boolean(orgId))
    })
    return () => {
      cancelled = true
    }
  }, [user])

  const enabled = Boolean(user) && orgReady

  const {
    data: pageContext,
    loadState,
    generatedAt,
    isValidating,
    mutate: mutateSnapshot,
    error,
  } = useIntelligenceSnapshot({ enabled, windowHours: 24 })

  // Outcome attribution: measured outcomes per agent and how many scoring needs.
  const { data: outcomes } = useSWR(
    enabled ? ["intelligence/outcomes", 7] : null,
    () => intelligenceApi.outcomes({ periodDays: 7 }),
    { revalidateOnFocus: false },
  )
  const { data: trust } = useSWR(enabled ? "intelligence/trust-summary" : null, () =>
    intelligenceApi.trustSummary({ periodDays: 7 }),
  )
  const { data: connectorsData, mutate: mutateConnectors } = useSWR(
    enabled ? "/api/connectors" : null,
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )
  // Patterns still being reinforced (any status; open ones are picked out downstream).
  const { data: candidatesData } = useSWR(
    enabled ? "intelligence/overview/memory-candidates" : null,
    () => memoryPromotionApi.candidates({ limit: 50 }),
    { revalidateOnFocus: false },
  )

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view intelligence." />
      </AppShell>
    )
  }

  if (!orgReady) {
    return (
      <AppShell title={copy.title}>
        <CenteredLoader label="Resolving workspace…" />
      </AppShell>
    )
  }

  if (error && !pageContext) {
    const isOrgDenied =
      error instanceof ApiError &&
      error.status === 403 &&
      /not a member of the requested organization/i.test(error.message)
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load intelligence"
          description={
            isOrgDenied
              ? "Your saved workspace no longer matches membership. We cleared it — try again, or pick an organization in Settings."
              : error instanceof ApiError
                ? error.message
                : "Try again in a moment."
          }
          onRetry={() => {
            if (isOrgDenied) {
              void ensureSelectedOrg(true).then(() => mutateSnapshot())
              return
            }
            mutateSnapshot()
          }}
        />
      </AppShell>
    )
  }

  const attribution = (outcomes?.v8_outcome_attribution as OutcomeAttribution | undefined) ?? null
  const avgConfidence = typeof trust?.avg_confidence === "number" ? trust.avg_confidence : null

  return (
    <AppShell title={copy.title}>
      <div className={PAGE_FRAME} data-composition="understand">
        <IntelligenceSectionRedirect />
        <GravitrePageHeader
          eyebrow="Understand / Evidence before answers"
          titleScale="display"
          title={copy.title}
          description={copy.description}
          actions={
            <AskGravitreSummonButton
              label="Ask about this page"
              selected={selected}
              prompt="Walk me through what Gravitre is learning right now: what signal came in today, which connections got stronger, and how close forecasts are to being scored."
              className="inline-flex items-center rounded-[10px] bg-foreground px-3.5 text-[13px] text-background hover:no-underline hover:opacity-90 dark:text-background"
            />
          }
        />
        <IntelligenceShell
          activeTab="overview"
          loadState={loadState}
          generatedAt={generatedAt}
          isValidating={isValidating}
          onRefresh={() => mutateSnapshot()}
        >
          <IntelligenceBrain
            pageContext={pageContext}
            connectors={connectorsData?.connectors ?? null}
            candidates={candidatesData?.items ?? null}
            attribution={attribution}
            avgConfidence={avgConfidence}
            loading={loadState === "LOADING" || loadState === "UNINITIALIZED"}
            onSelectionChange={setSelected}
            onResynced={() => {
              void mutateConnectors()
              mutateSnapshot()
            }}
          />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}

export default function IntelligenceCenterPage() {
  return (
    <Suspense
      fallback={
        <AppShell title={SURFACE_COPY.insights.title}>
          <CenteredLoader fill="parent" label="Loading intelligence" />
        </AppShell>
      }
    >
      <IntelligenceCenterInner />
    </Suspense>
  )
}
