"use client"

import { Suspense, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { CalendarBlank, Sparkle } from "@phosphor-icons/react"
import { AppShell } from "@/components/gravitre/app-shell"
import { usePublishGravitreAISelection, type GravitreAISelectedEntity } from "@/components/gravitre/ai-workspace-provider"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import {
  EVIDENCE_FEED_PREFIX,
  EvidenceRecommendationSheet,
  evidenceFeedItems,
  useEvidenceRecommendations,
} from "@/components/intelligence/evidence-play-recommendations"
import type { FailureAlertWithEvidence } from "@/components/intelligence/forecasts/forecast-model"
import { toast } from "@/components/intelligence/overlays/toast"
import { ShareFindingDialog, type ShareableFinding } from "@/components/intelligence/overlays/share-finding-dialog"
import { RevenueOpportunitiesSheet } from "@/components/intelligence/overview/revenue-opportunities-sheet"
import {
  ABILITY_MODES,
  OVERVIEW_PERIODS,
  attentionItems,
  buildFeed,
  candidateEvidence,
  candidatesInWindow,
  connectedApps,
  dataReadiness,
  glanceCards,
  overviewForecasts,
  pageMetrics,
  pendingCandidates,
  sevenAbilities,
  thinkingSummary,
  type FeedItem,
  type OverviewPeriod,
} from "@/components/intelligence/overview/overview-model"
import {
  AtAGlance,
  AttentionCard,
  DataReadinessCard,
  HowGravitreThinks,
  KnowsCard,
  LearningCard,
  RecentActivity,
} from "@/components/intelligence/overview/overview-sections"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  connectorsApi,
  enterpriseApi,
  intelligenceApi,
  intelligenceFindingsApi,
  memoryPromotionApi,
  workflowsApi,
  type IntelligenceAbilityMode,
  type IntelligenceAbilityName,
} from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { ensureSelectedOrg, getQuickOrgId } from "@/lib/org-context"
import { readCachedOrgMembership, writeCachedOrgMembership } from "@/lib/org-gate-cache"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { INTELLIGENCE_PAGE_FRAME } from "@/lib/design-system"
import { SURFACE_COPY } from "@/lib/surface-copy"

/** Same SWR key as Forecasts and Activity › Failures so all three share one cache entry. */
const FAILURE_ALERTS_KEY = ["workflow-failure-predictions", "open"] as const
const MEMORY_HREF = `${APP_ROUTES.learning}?view=memory`

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

const ANALYZE_TOAST_ID = "overview-analyze"
const FEED_ANCHOR = "overview-recent-activity"

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
  const [period, setPeriod] = useState<OverviewPeriod>("week")
  const [analyzing, setAnalyzing] = useState(false)
  const [savingAbility, setSavingAbility] = useState<IntelligenceAbilityName | null>(null)
  const { isAdmin } = useOrgAdmin()
  // The activity item under the pointer or focus becomes Ask Gravitre's context.
  const [selected, setSelected] = useState<GravitreAISelectedEntity | null>(null)
  usePublishGravitreAISelection(selected)
  const [revenueOpen, setRevenueOpen] = useState(false)
  const [refreshingRevenue, setRefreshingRevenue] = useState(false)
  const [sharing, setSharing] = useState<ShareableFinding | null>(null)
  const periodInfo = OVERVIEW_PERIODS[period]

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
    mutate: mutateSnapshot,
    error,
  } = useIntelligenceSnapshot({
    enabled,
    windowHours: periodInfo.windowHours,
    swrKeySuffix: orgId ?? undefined,
  })
  const { data: roi, isLoading: roiLoading, mutate: mutateRoi } = useSWR(
    enabled ? ["intelligence/overview/agent-roi", orgId, periodInfo.roiDays] : null,
    () => enterpriseApi.getAgentRoi({ periodDays: periodInfo.roiDays }),
    { revalidateOnFocus: false, keepPreviousData: true },
  )
  const { data: connectorsData, isLoading: connectorsLoading, mutate: mutateConnectors } = useSWR(
    enabled ? ["/api/connectors", orgId] : null,
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )
  // Patterns still being reinforced (any status; pending ones are picked out downstream). Admin only.
  const { data: candidatesData, mutate: mutateCandidates } = useSWR(
    enabled ? ["intelligence/overview/memory-candidates", orgId] : null,
    () => memoryPromotionApi.candidates({ limit: 50 }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  // Tenant Overview contract: readiness and the seven ability settings.
  const { data: overview, mutate: mutateOverview } = useSWR(
    enabled ? ["intelligence/overview/contract", orgId] : null,
    () => intelligenceApi.overview(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  const { data: heuristics, mutate: mutateHeuristics } = useSWR(
    enabled ? ["intelligence/overview/heuristics", orgId] : null,
    () => intelligenceApi.heuristicRecommendations(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  // Open HubSpot deal value (Revenue opportunities); the backend caches it for ten minutes.
  const { data: opportunities, mutate: mutateOpportunities } = useSWR(
    enabled ? ["intelligence/overview/revenue-opportunities", orgId] : null,
    () => intelligenceFindingsApi.revenueOpportunities(),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )
  // Same key as Forecasts and Activity › Failures, so the three share one cache entry.
  const { data: alerts, mutate: mutateAlerts } = useSWR(
    enabled ? FAILURE_ALERTS_KEY : null,
    () => workflowsApi.listFailurePredictions({ status: "open" }),
    { revalidateOnFocus: false, shouldRetryOnError: false },
  )

  // The requests above went out under the optimistic org. If background
  // membership resolution lands on a different one, refetch under it.
  const lastOrgRef = useRef(orgId)
  useEffect(() => {
    const previous = lastOrgRef.current
    lastOrgRef.current = orgId
    if (!previous || !orgId || previous === orgId) return
    mutateSnapshot()
    void mutateRoi()
    void mutateConnectors()
    void mutateCandidates()
    void mutateHeuristics()
    void mutateAlerts()
    void mutateOverview()
    void mutateOpportunities()
  }, [
    orgId,
    mutateSnapshot,
    mutateRoi,
    mutateConnectors,
    mutateCandidates,
    mutateHeuristics,
    mutateAlerts,
    mutateOverview,
    mutateOpportunities,
  ])

  const metrics = pageMetrics(pageContext)
  const snapshotLoading = loadState === "LOADING" || loadState === "UNINITIALIZED"
  const connectors = connectorsData?.connectors ?? null
  const apps = useMemo(() => connectedApps(connectors), [connectors])
  const forecasts = useMemo(
    () => overviewForecasts(pageContext, alerts?.alerts as FailureAlertWithEvidence[] | undefined),
    [pageContext, alerts],
  )
  const candidates = candidatesData?.items ?? null
  const pending = useMemo(() => pendingCandidates(candidates), [candidates])
  const fresh = useMemo(
    () => candidatesInWindow(candidates, periodInfo.windowHours),
    [candidates, periodInfo.windowHours],
  )
  const topPattern = pending[0] ?? null
  const readiness = useMemo(
    () => dataReadiness({ connectors, readiness: overview?.readiness ?? null }),
    [connectors, overview],
  )
  const abilities = useMemo(() => sevenAbilities(overview?.capabilities), [overview])
  const glance = useMemo(
    () =>
      glanceCards({
        roi,
        metrics,
        opportunities,
        routes: {
          impact: APP_ROUTES.intelligencePerformance,
          reports: APP_ROUTES.intelligenceReports,
          approvals: APP_ROUTES.approvals,
          plays: APP_ROUTES.plays,
          connectors: APP_ROUTES.connectors,
        },
      }),
    [roi, metrics, opportunities],
  )
  const attention = useMemo(
    () =>
      attentionItems({
        connectors,
        metrics,
        pending,
        forecasts,
        routes: {
          connectors: APP_ROUTES.connectors,
          approvals: APP_ROUTES.approvals,
          memory: MEMORY_HREF,
          forecasts: APP_ROUTES.intelligencePredictive,
        },
      }),
    [connectors, metrics, pending, forecasts],
  )
  const evidence = useEvidenceRecommendations(enabled, orgId ?? null)
  const [reviewingEvidence, setReviewingEvidence] = useState<string | null>(null)
  const feed = useMemo(
    () => [
      ...evidenceFeedItems(evidence.recommendations, evidence.plays),
      ...buildFeed({
        ctx: pageContext,
        forecasts,
        cards: heuristics?.recommendations ?? null,
        routes: {
          forecasts: APP_ROUTES.intelligencePredictive,
          activity: APP_ROUTES.activity,
          reports: APP_ROUTES.intelligenceReports,
          memory: MEMORY_HREF,
        },
      }),
    ],
    [pageContext, forecasts, heuristics, evidence.recommendations, evidence.plays],
  )
  const hours = glance.find((card) => card.id === "hours")?.value ?? null
  const revenue = glance.find((card) => card.id === "revenue")?.value ?? null
  const summary = thinkingSummary({
    phrase: periodInfo.phrase,
    forecasts,
    hours,
    revenue,
    currency: opportunities?.currency,
  })

  const findingKeys = (items: FeedItem[]) => new Set(items.filter((i) => i.kind !== "action" && i.kind !== "outcome").map((i) => i.id))

  async function analyzeBusiness() {
    if (analyzing) return
    setAnalyzing(true)
    const before = findingKeys(feed)
    toast.loading("Analyzing your business", {
      id: ANALYZE_TOAST_ID,
      eyebrow: "Sweep running",
      description: "Re-reading every connected app, forecast and suggestion.",
    })
    try {
      // Re-read every producer behind the snapshot (skipping its short cache) and
      // check every workflow for likely failures, then refresh what the page shows.
      // Admins also queue the tenant's durable sweep. It is opt-in on the server:
      // when the worker is off (503) or nothing is connected (409) the re-read
      // below is the whole analysis; at the daily limit (429) we say so.
      const sweep = isAdmin
        ? intelligenceApi.requestOverviewSweep().then(
            () => "queued" as const,
            (err: unknown) => (err instanceof ApiError && err.status === 429 ? ("limit" as const) : null),
          )
        : Promise.resolve(null)
      const [fresh, , nextCards, nextAlerts, sweepState] = await Promise.all([
        intelligenceApi.pageContext({ windowHours: periodInfo.windowHours, refresh: true }),
        workflowsApi.scanAllFailurePredictions().catch(() => null),
        intelligenceApi.heuristicRecommendations().catch(() => null),
        workflowsApi.listFailurePredictions({ status: "open" }).catch(() => null),
        sweep,
      ])
      mutateSnapshot()
      void mutateOverview()
      void mutateHeuristics(nextCards ?? undefined, { revalidate: !nextCards })
      void mutateAlerts(nextAlerts ?? undefined, { revalidate: !nextAlerts })
      void mutateCandidates()
      void mutateRoi()
      const after = buildFeed({
        ctx: fresh,
        forecasts: overviewForecasts(fresh, (nextAlerts?.alerts ?? alerts?.alerts) as FailureAlertWithEvidence[] | undefined),
        cards: nextCards?.recommendations ?? heuristics?.recommendations ?? null,
        routes: { forecasts: "", activity: "", reports: "", memory: "" },
      })
      const added = [...findingKeys(after)].filter((key) => !before.has(key)).length
      toast.success("Analyze my business finished", {
        id: ANALYZE_TOAST_ID,
        eyebrow: "Sweep complete",
        description: [
          added > 0
            ? `${added} new ${added === 1 ? "finding was" : "findings were"} added to Recent insights.`
            : "Nothing new turned up. Recent insights are up to date.",
          sweepState === "queued" ? "A deeper sweep across your apps is queued." : "",
          sweepState === "limit" ? "Today's deeper sweeps are used up; the next one runs tomorrow." : "",
        ]
          .filter(Boolean)
          .join(" "),
        action: {
          label: "View findings",
          onClick: () => document.getElementById(FEED_ANCHOR)?.scrollIntoView({ behavior: "smooth", block: "start" }),
        },
        cancel: { label: "Dismiss", onClick: () => {} },
      })
    } catch (err) {
      toast.error("Couldn't finish the analysis", {
        id: ANALYZE_TOAST_ID,
        eyebrow: "Sweep stopped",
        description: err instanceof ApiError ? err.message : "Try again in a moment. Nothing was changed.",
      })
    } finally {
      setAnalyzing(false)
    }
  }

  async function changeAbility(id: IntelligenceAbilityName, mode: IntelligenceAbilityMode) {
    if (!isAdmin || savingAbility) return
    const label = abilities.find((ability) => ability.id === id)?.label ?? "Ability"
    setSavingAbility(id)
    try {
      const saved = await intelligenceApi.updateOverviewProfile({ [id]: { mode } })
      await mutateOverview(overview ? { ...overview, capabilities: saved.capabilities } : undefined, { revalidate: !overview })
      toast.success(`${label} set to ${ABILITY_MODES.find((m) => m.id === mode)?.label.toLowerCase()}`, {
        description: "Gravitre uses this on the next question. Nothing runs on its own.",
      })
    } catch (err) {
      toast.error(`Couldn't change ${label.toLowerCase()}`, {
        description: err instanceof ApiError ? err.message : "Your previous setting is still in place.",
      })
    } finally {
      setSavingAbility(null)
    }
  }

  async function dismissCard(cardId: string) {
    try {
      await intelligenceApi.dismissHeuristicRecommendation(cardId)
      await mutateHeuristics()
      toast.success("Suggestion dismissed", { description: "Gravitre won't show it again." })
    } catch {
      toast.error("Couldn't dismiss that suggestion")
    }
  }

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

  const knowledge = metrics?.knowledge ?? {}
  const execution = metrics?.execution ?? {}
  const readyNumber = (value: unknown) => (snapshotLoading ? null : typeof value === "number" ? value : null)

  return (
    <AppShell title={copy.title}>
      <div className={INTELLIGENCE_PAGE_FRAME} data-composition="understand">
        <IntelligenceSectionRedirect />
        <GravitrePageHeader
          titleScale="display"
          title={copy.title}
          description={`What Gravitre knows about your business, what it is learning, and what it did with it ${periodInfo.phrase}.`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="h-10 rounded-[12px] px-3.5">
                    <CalendarBlank className="mr-1.5 h-4 w-4" weight="bold" aria-hidden />
                    {periodInfo.label}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  {(Object.keys(OVERVIEW_PERIODS) as OverviewPeriod[]).map((id) => (
                    <DropdownMenuItem key={id} onSelect={() => setPeriod(id)}>
                      {OVERVIEW_PERIODS[id].label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <AskGravitreSummonButton
                label="Ask Gravitre"
                prompt={`Walk me through what changed ${periodInfo.phrase}: which signals came in from my connected tools, and what they mean.`}
                className="inline-flex h-10 min-h-10 items-center rounded-[12px] border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3.5 text-[13px] font-medium text-[color:var(--g-text-primary)] hover:no-underline hover:bg-[color:var(--g-surface-2)] dark:text-[color:var(--g-text-primary)]"
              />
              <Button
                className="h-10 rounded-[12px] bg-[color:var(--g-brand-active)] px-4 text-white hover:bg-[color:var(--g-brand-hover)]"
                onClick={() => void analyzeBusiness()}
                disabled={analyzing || !enabled}
              >
                <Sparkle className={`mr-1.5 h-4 w-4 ${analyzing ? "animate-pulse" : ""}`} weight="fill" aria-hidden />
                {analyzing ? "Analyzing…" : "Analyze my business"}
              </Button>
            </div>
          }
        />
        <IntelligenceShell activeTab="overview" loadState={loadState} generatedAt={generatedAt}>
          {orgId === null ? (
            <EmptyState
              title="No workspace selected"
              description="Pick an organization in Settings to see what Gravitre is learning."
            />
          ) : (
            <div className="space-y-8 pt-2">
              <DataReadinessCard
                readiness={readiness}
                loading={(connectorsLoading && !connectors) || snapshotLoading}
                href={APP_ROUTES.connectors}
              />
              <div className="space-y-3">
                <AtAGlance
                  cards={glance}
                  loading={(roiLoading && !roi) || snapshotLoading}
                  phrase={periodInfo.phrase}
                  onOpenEvidence={(id) => {
                    if (id === "revenue") setRevenueOpen(true)
                  }}
                />
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                  <KnowsCard
                    entities={readyNumber(knowledge.knownEntities)}
                    relationships={readyNumber(knowledge.knownRelationships)}
                    apps={apps}
                    updatedAt={generatedAt}
                    loading={snapshotLoading}
                    href={APP_ROUTES.learning}
                  />
                  <LearningCard
                    newCount={candidates ? fresh.length : null}
                    phrase={periodInfo.phrase}
                    top={topPattern}
                    topEvidence={topPattern ? candidateEvidence(topPattern) : ""}
                    pendingCount={pending.length}
                    loading={!candidatesData && snapshotLoading}
                    href={MEMORY_HREF}
                  />
                  <AttentionCard items={attention} loading={snapshotLoading && !connectors} />
                </div>
              </div>
              <HowGravitreThinks
                apps={apps}
                entities={readyNumber(knowledge.knownEntities)}
                recommendations={readyNumber(execution.recommendationsCreated)}
                actions={readyNumber(execution.actionsCompleted)}
                awaiting={readyNumber(execution.awaitingApproval)}
                summary={snapshotLoading ? null : summary}
                routes={{ knowledge: APP_ROUTES.learning, activity: APP_ROUTES.activity }}
                abilities={abilities}
                onModeChange={isAdmin && overview ? (id, mode) => void changeAbility(id, mode) : undefined}
                savingAbility={savingAbility}
              />
              <RecentActivity
                id={FEED_ANCHOR}
                items={feed}
                loading={snapshotLoading}
                onDismiss={(cardId) => void dismissCard(cardId)}
                onReview={(item) => {
                  if (!item.id.startsWith(EVIDENCE_FEED_PREFIX)) return false
                  setReviewingEvidence(item.id.slice(EVIDENCE_FEED_PREFIX.length))
                  return true
                }}
                onSelect={(item) => setSelected({ kind: `intelligence-${item.kind}`, id: item.id, label: item.title })}
                onShare={(item) =>
                  setSharing({
                    id: item.id,
                    title: item.title,
                    summary: item.detail,
                    path: item.href.startsWith("/") ? item.href : APP_ROUTES.intelligencePredictive,
                  })
                }
              />
              <EvidenceRecommendationSheet
                recommendation={evidence.recommendations.find((item) => item.id === reviewingEvidence) ?? null}
                plays={evidence.plays}
                onOpenChange={(open) => {
                  if (!open) setReviewingEvidence(null)
                }}
                onChanged={() => void evidence.refresh()}
              />
              <RevenueOpportunitiesSheet
                open={revenueOpen}
                onOpenChange={setRevenueOpen}
                data={opportunities}
                refreshing={refreshingRevenue}
                connectorsHref={APP_ROUTES.connectors}
                onRefresh={() => {
                  setRefreshingRevenue(true)
                  void intelligenceFindingsApi
                    .revenueOpportunities(true)
                    .then((fresh) => mutateOpportunities(fresh, { revalidate: false }))
                    .catch(() => toast.error("HubSpot couldn't be read just now. Try again in a moment."))
                    .finally(() => setRefreshingRevenue(false))
                }}
              />
              <ShareFindingDialog
                finding={sharing}
                onOpenChange={(open) => {
                  if (!open) setSharing(null)
                }}
              />
            </div>
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
