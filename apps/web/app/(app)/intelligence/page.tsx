"use client"

import { Suspense, useEffect, useRef, useState } from "react"
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
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import { readCachedOrgMembership, writeCachedOrgMembership } from "@/lib/org-gate-cache"
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
  const userId = user?.id ?? null
  const copy = SURFACE_COPY.insights
  // Org gate, optimistic: when the stored org selection is the one membership
  // resolution last confirmed for this user, start loading immediately and
  // revalidate membership in the background (the forced organizations list
  // used to hold a full-page "Resolving workspace" loader first). `undefined`
  // = not known yet, `null` = the user has no workspace.
  const [orgId, setOrgId] = useState<string | null | undefined>(() => {
    const quick = getQuickOrgId()
    return quick && userId && readCachedOrgMembership(userId) === quick ? quick : undefined
  })
  const [selected, setSelected] = useState<GravitreAISelectedEntity | null>(null)
  usePublishGravitreAISelection(selected)

  useEffect(() => {
    if (!userId) {
      setOrgId(undefined)
      return
    }
    let cancelled = false
    void ensureSelectedOrg().then((resolved) => {
      if (cancelled) return
      writeCachedOrgMembership(userId, resolved)
      setOrgId(resolved)
    })
    return () => {
      cancelled = true
    }
  }, [userId])

  const orgReady = Boolean(orgId)
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
  const { data: outcomes, mutate: mutateOutcomes } = useSWR(
    enabled ? ["intelligence/outcomes", 7] : null,
    () => intelligenceApi.outcomes({ periodDays: 7 }),
    { revalidateOnFocus: false },
  )
  const { data: trust, mutate: mutateTrust } = useSWR(enabled ? "intelligence/trust-summary" : null, () =>
    intelligenceApi.trustSummary({ periodDays: 7 }),
  )
  const { data: connectorsData, mutate: mutateConnectors } = useSWR(
    enabled ? "/api/connectors" : null,
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )
  // Patterns still being reinforced (any status; open ones are picked out downstream).
  const { data: candidatesData, mutate: mutateCandidates } = useSWR(
    enabled ? "intelligence/overview/memory-candidates" : null,
    () => memoryPromotionApi.candidates({ limit: 50 }),
    { revalidateOnFocus: false },
  )

  // The requests above went out under the optimistic org. If background
  // membership resolution lands on a different one, refetch under it.
  const lastOrgRef = useRef(orgId)
  useEffect(() => {
    const previous = lastOrgRef.current
    lastOrgRef.current = orgId
    if (!previous || !orgId || previous === orgId) return
    mutateSnapshot()
    void mutateOutcomes()
    void mutateTrust()
    void mutateConnectors()
    void mutateCandidates()
  }, [orgId, mutateSnapshot, mutateOutcomes, mutateTrust, mutateConnectors, mutateCandidates])

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view intelligence." />
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
          {orgId === null ? (
            <EmptyState
              title="No workspace selected"
              description="Pick an organization in Settings to see what Gravitre is learning."
            />
          ) : (
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
          )}
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
