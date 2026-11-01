"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { usePublishGravitreAISelection, type GravitreAISelectedEntity } from "@/components/gravitre/ai-workspace-provider"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { evidenceFeedItems, useEvidenceRecommendations } from "@/components/intelligence/evidence-play-recommendations"
import type { FailureAlertWithEvidence } from "@/components/intelligence/forecasts/forecast-model"
import { formatHours, impactTotals, metricNumber } from "@/components/intelligence/impact/impact-model"
import { toast } from "@/components/intelligence/overlays/toast"
import {
  OverviewDrawer,
  type EvidenceView,
  type OverviewDrawerState,
} from "@/components/intelligence/overview/overview-drawer"
import {
  ABILITY_MODES,
  OVERVIEW_PERIODS,
  attentionItems,
  buildFeed,
  candidateEvidence,
  candidatesInWindow,
  connectedApps,
  dataReadiness,
  formatMoneyCompact,
  glanceCards,
  overviewForecasts,
  pageMetrics,
  pendingCandidates,
  readinessAreas,
  sevenAbilities,
  thinkingSummary,
  type FeedItem,
  type FeedKind,
  type GlanceCard,
  type OverviewPeriod,
} from "@/components/intelligence/overview/overview-model"
import {
  AtAGlance,
  AttentionCard,
  DataReadinessCard,
  HowGravitreThinks,
  Ico,
  KnowsCard,
  LearningCard,
  PATHS,
  RecentActivity,
  glanceValue,
  type SweepStep,
  type SweepView,
} from "@/components/intelligence/overview/overview-sections"
import { IntelligenceShell } from "@/components/intelligence/shell"
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

function humanizeKind(value: string): string {
  const text = value.replace(/[_-]+/g, " ").trim()
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : ""
}

function shortDay(value: string): string {
  const at = Date.parse(value)
  return Number.isFinite(at) ? new Date(at).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : value
}
const FEED_ANCHOR = "overview-recent-activity"

function IntelligenceCenterInner() {
  const { user } = useAuth()
  const userId = user?.id ?? null
  const copy = SURFACE_COPY.insights
  const router = useRouter()
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
  const [savingAbility, setSavingAbility] = useState<IntelligenceAbilityName | null>(null)
  const { isAdmin } = useOrgAdmin()
  // The activity item under the pointer or focus becomes Ask Gravitre's context.
  const [selected, setSelected] = useState<GravitreAISelectedEntity | null>(null)
  usePublishGravitreAISelection(selected)
  const [drawer, setDrawer] = useState<OverviewDrawerState | null>(null)
  const [filter, setFilter] = useState<FeedKind | "all">("all")
  const [sweep, setSweep] = useState<SweepView>({ status: "idle" })
  const [newIds, setNewIds] = useState<Set<string>>(() => new Set())
  const periodInfo = OVERVIEW_PERIODS[period]
  const closeDrawer = useCallback(() => setDrawer(null), [])

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
  // What Gravitre has learned: memories in use and waiting (any status). Admin only.
  const {
    data: candidatesData,
    error: candidatesError,
    mutate: mutateCandidates,
  } = useSWR(
    enabled ? ["intelligence/overview/memory-candidates", orgId] : null,
    () => memoryPromotionApi.candidates({ limit: 100 }),
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
  const areas = useMemo(
    () => readinessAreas({ connectors, readiness: overview?.readiness ?? null }),
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

  const openItem = useCallback((item: FeedItem) => setDrawer({ type: "item", item }), [])

  /** The records behind each "At a glance" number, for the evidence panel. */
  function evidenceFor(id: GlanceCard["id"]): EvidenceView {
    const card = glance.find((c) => c.id === id)
    const value = (card && glanceValue(card)) ?? "—"
    if (id === "revenue") {
      const ready = opportunities?.status === "ready"
      return {
        label: "Revenue opportunities",
        value,
        unit: ready ? `open in the next ${opportunities.lookaheadDays} days` : "not available yet",
        summary:
          "Gravitre found these from open deals in your CRM. It counts only amounts recorded there, never estimates of what a deal might grow to.",
        rows: ready
          ? opportunities.rows.map((row) => ({
              key: row.id,
              label: row.label,
              src: [humanizeKind(row.kind), row.source, row.closeDate ? `closes ${shortDay(row.closeDate)}` : ""].filter(Boolean).join(" · "),
              value: formatMoneyCompact(row.amount, row.currency),
              href: row.href ?? undefined,
            }))
          : [],
        empty: card?.hint ?? "Reading open deals from your CRM…",
        method:
          opportunities?.method ||
          "Sum of open deal amounts closing soon. Money owed on overdue invoices is counted separately, not as new revenue.",
        link: ready ? undefined : { label: card?.link.label ?? "Open Connectors", href: APP_ROUTES.connectors },
      }
    }
    if (id === "hours") {
      const rows = (roi?.agents ?? [])
        .map((agent) => ({ agent, saved: metricNumber(agent.estimatedHoursSaved), tasks: metricNumber(agent.tasksCompleted) }))
        .filter((row) => row.saved != null && row.saved > 0)
        .map(({ agent, saved, tasks }) => ({
          key: agent.agentId,
          label: agent.agentName || "Unassigned work",
          src: tasks != null ? `${tasks.toLocaleString("en-US")} finished ${tasks === 1 ? "task" : "tasks"} · estimated from task type` : "Estimated from task type",
          value: formatHours(saved).replace(" h", " hrs"),
        }))
      const tasks = impactTotals(roi).tasks
      return {
        label: "Hours potentially saved",
        value,
        unit: `of team work ${periodInfo.phrase}`,
        summary:
          "An estimate of the time your team would have spent doing the same work by hand. Only tasks that finished are counted.",
        rows,
        empty: tasks ? "No agent recorded time saved yet." : "Fills in once an agent finishes a task.",
        method:
          roi?.methodology ||
          "For each finished task, the typical time that kind of task takes by hand. Shown as potential because people may still spend some of that time reviewing.",
        link: { label: "Open Impact", href: APP_ROUTES.intelligencePerformance },
      }
    }
    if (id === "resolved") {
      const rows = feed
        .filter((item) => item.kind === "outcome")
        .slice(0, 8)
        .map((item) => ({ key: item.id, label: item.title, src: item.detail, value: "Recorded", open: () => openItem(item) }))
      return {
        label: "Issues resolved",
        value,
        unit: "resolved and confirmed",
        summary: "Issues count as resolved only when a result was recorded. Gravitre does not count work that is still in progress.",
        rows,
        empty: "No confirmed results yet.",
        method:
          "Counted from the outcome ledger: a result your connected apps recorded after the work, such as a reply, a booked meeting or a metric back to normal.",
        link: { label: "Open Reports", href: APP_ROUTES.intelligenceReports },
      }
    }
    const runs = attention.find((a) => a.id === "approvals")
    return {
      label: "Awaiting approval",
      value,
      unit: card?.value === 1 ? "action waiting for you" : "actions waiting for you",
      summary: "These are ready to run but wait for a person, based on the approval rules for each play and workflow.",
      rows: [
        ...(runs ? [{ key: "runs", label: runs.text, src: "Workflow approvals", value: "Review", open: () => router.push(APP_ROUTES.approvals) }] : []),
        ...pending.slice(0, 6).map((c) => ({
          key: c.id,
          label: String(c.content ?? ""),
          src: "Pattern waiting for review",
          value: "Review",
          open: () => setDrawer({ type: "know", view: "waiting" }),
        })),
      ],
      empty: "Nothing is waiting. All caught up.",
      method: "Counts workflow runs and learned patterns that are fully prepared and blocked only on approval.",
      link: { label: "Open approvals", href: APP_ROUTES.approvals },
    }
  }

  const findingKeys = (items: FeedItem[]) => new Set(items.filter((i) => i.kind !== "action" && i.kind !== "outcome").map((i) => i.id))

  async function analyzeBusiness() {
    if (sweep.status === "running") return
    const before = findingKeys(feed)
    // Every stage below runs for real; the banner shows each one as it finishes.
    const names = ["Connected apps", "Workflows", "Suggestions", "Forecasts", ...(isAdmin ? ["Deeper sweep"] : [])]
    const finished = new Set<string>()
    const show = () =>
      setSweep({
        status: "running",
        pct: Math.round((finished.size / names.length) * 100),
        steps: names.map((name): SweepStep => ({ name, state: finished.has(name) ? "done" : "on" })),
      })
    const track = <T,>(name: string, work: Promise<T>) =>
      work.finally(() => {
        finished.add(name)
        show()
      })
    setFilter("all")
    setNewIds(new Set())
    show()
    try {
      // Re-read every producer behind the snapshot (skipping its short cache) and
      // check every workflow for likely failures, then refresh what the page shows.
      // Admins also queue the tenant's durable sweep. It is opt-in on the server:
      // when the worker is off (503) or nothing is connected (409) the re-read
      // below is the whole analysis; at the daily limit (429) we say so.
      const deeper = isAdmin
        ? track(
            "Deeper sweep",
            intelligenceApi.requestOverviewSweep().then(
              () => "queued" as const,
              (err: unknown) => (err instanceof ApiError && err.status === 429 ? ("limit" as const) : null),
            ),
          )
        : Promise.resolve(null)
      const [freshCtx, , nextCards, nextAlerts, sweepState] = await Promise.all([
        track("Connected apps", intelligenceApi.pageContext({ windowHours: periodInfo.windowHours, refresh: true })),
        track("Workflows", workflowsApi.scanAllFailurePredictions().catch(() => null)),
        track("Suggestions", intelligenceApi.heuristicRecommendations().catch(() => null)),
        track("Forecasts", workflowsApi.listFailurePredictions({ status: "open" }).catch(() => null)),
        deeper,
      ])
      mutateSnapshot()
      void mutateOverview()
      void mutateHeuristics(nextCards ?? undefined, { revalidate: !nextCards })
      void mutateAlerts(nextAlerts ?? undefined, { revalidate: !nextAlerts })
      void mutateCandidates()
      void mutateRoi()
      const after = buildFeed({
        ctx: freshCtx,
        forecasts: overviewForecasts(freshCtx, (nextAlerts?.alerts ?? alerts?.alerts) as FailureAlertWithEvidence[] | undefined),
        cards: nextCards?.recommendations ?? heuristics?.recommendations ?? null,
        routes: { forecasts: "", activity: "", reports: "", memory: "" },
      })
      const added = [...findingKeys(after)].filter((key) => !before.has(key))
      setNewIds(new Set(added))
      const kinds = after.filter((item) => added.includes(item.id))
      const insights = kinds.filter((item) => item.kind === "insight").length
      const recs = kinds.filter((item) => item.kind === "recommendation").length
      const found = [
        insights ? `${insights} new ${insights === 1 ? "insight" : "insights"}` : "",
        recs ? `${recs} ${recs === 1 ? "recommendation" : "recommendations"}` : "",
      ].filter(Boolean)
      setSweep({
        status: "done",
        text: [
          found.length
            ? `Business analysis finished just now. It found ${found.join(" and ")}, marked New below.`
            : "Business analysis finished just now. Nothing new turned up, so recent insights are up to date.",
          sweepState === "queued" ? "A deeper sweep across your apps is queued." : "",
          sweepState === "limit" ? "Today's deeper sweeps are used up; the next one runs tomorrow." : "",
        ]
          .filter(Boolean)
          .join(" "),
      })
    } catch (err) {
      setSweep({ status: "idle" })
      toast.error("Couldn't finish the analysis", {
        id: ANALYZE_TOAST_ID,
        eyebrow: "Analysis stopped",
        description: err instanceof ApiError ? err.message : "Try again in a moment. Nothing was changed.",
      })
    }
  }

  async function changeAbility(id: IntelligenceAbilityName, patch: { mode: IntelligenceAbilityMode; enabled: boolean }) {
    if (!isAdmin || savingAbility) return
    const ability = abilities.find((a) => a.id === id)
    const label = ability?.label ?? "Ability"
    setSavingAbility(id)
    try {
      const saved = await intelligenceApi.updateOverviewProfile({ [id]: patch })
      await mutateOverview(overview ? { ...overview, capabilities: saved.capabilities } : undefined, { revalidate: !overview })
      toast.success(
        ability && ability.enabled !== patch.enabled
          ? `${label} turned ${patch.enabled ? "on" : "off"}`
          : `${label} set to ${ABILITY_MODES.find((m) => m.id === patch.mode)?.label.toLowerCase()}`,
        { description: "Gravitre uses this on the next question. Nothing runs on its own." },
      )
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
    } catch (err) {
      toast.error("Couldn't dismiss that suggestion")
      throw err
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
  const running = sweep.status === "running"

  return (
    <AppShell title={copy.title}>
      <div className={`${INTELLIGENCE_PAGE_FRAME} io-root`} data-composition="understand">
        <IntelligenceSectionRedirect />
        <GravitrePageHeader
          titleScale="display"
          title={copy.title}
          description={`What Gravitre knows about your business, what it is learning, and what it did with it ${periodInfo.phrase}.`}
          actions={
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="io-btn" style={{ minHeight: 40 }}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                      <rect x="3.5" y="5" width="17" height="15" rx="2" />
                      <path d="M3.5 10h17M8 3v4M16 3v4" />
                    </svg>
                    {periodInfo.label}
                  </button>
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
                className="io-btn min-h-10 hover:no-underline"
                icon={<Ico d={PATHS.chat} size={14} width={1.8} />}
              />
              <button
                type="button"
                className="sw-hbtn"
                onClick={() => void analyzeBusiness()}
                disabled={running || !enabled}
                title={`Re-reads ${apps.length ? `all ${apps.length} connected ${apps.length === 1 ? "app" : "apps"}` : "your connected apps"}, using only data you are allowed to see.`}
              >
                <Ico d={PATHS.spark} size={16} />
                {running
                  ? `Analyzing… ${sweep.pct}%`
                  : sweep.status === "done"
                    ? "Analyze again"
                    : "Analyze my business"}
              </button>
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
            <div style={{ display: "flex", flexDirection: "column", gap: 40, paddingTop: 8 }}>
              <DataReadinessCard
                readiness={readiness}
                areas={areas}
                loading={(connectorsLoading && !connectors) || snapshotLoading}
                href={APP_ROUTES.connectors}
              />
              <AtAGlance
                cards={glance}
                loading={(roiLoading && !roi) || snapshotLoading}
                phrase={periodInfo.phrase}
                onOpen={(id) => setDrawer({ type: "evidence", id })}
              >
                <KnowsCard
                  entities={readyNumber(knowledge.knownEntities)}
                  relationships={readyNumber(knowledge.knownRelationships)}
                  apps={apps}
                  updatedAt={generatedAt}
                  loading={snapshotLoading}
                  onOpen={() => setDrawer({ type: "know" })}
                />
                <LearningCard
                  newCount={candidates ? fresh.length : null}
                  phrase={periodInfo.phrase}
                  top={topPattern}
                  topEvidence={topPattern ? candidateEvidence(topPattern) : ""}
                  pendingCount={pending.length}
                  loading={!candidatesData && snapshotLoading}
                  onOpen={() => setDrawer({ type: "know", view: pending.length > 0 ? "waiting" : "all" })}
                />
                <AttentionCard
                  items={attention}
                  loading={snapshotLoading && !connectors}
                  onAction={(item) => {
                    if (item.id !== "memory") return false
                    setDrawer({ type: "know", view: "waiting" })
                    return true
                  }}
                />
              </AtAGlance>
              <HowGravitreThinks
                apps={apps}
                entities={readyNumber(knowledge.knownEntities)}
                recommendations={readyNumber(execution.recommendationsCreated)}
                actions={readyNumber(execution.actionsCompleted)}
                awaiting={readyNumber(execution.awaitingApproval)}
                summary={snapshotLoading ? null : summary}
                abilities={abilities}
                onOpenKnowledge={() => setDrawer({ type: "know" })}
                onOpenAbility={(ability) => setDrawer({ type: "ability", id: ability.id })}
                onSeeActivity={() => {
                  setFilter("action")
                  document.getElementById(FEED_ANCHOR)?.scrollIntoView({ behavior: "smooth", block: "start" })
                }}
              />
              <RecentActivity
                id={FEED_ANCHOR}
                items={feed}
                loading={snapshotLoading}
                filter={filter}
                onFilter={setFilter}
                sweep={sweep}
                newIds={newIds}
                onOpen={openItem}
                onSelect={(item) => setSelected({ kind: `intelligence-${item.kind}`, id: item.id, label: item.title })}
              />
              <OverviewDrawer
                state={drawer}
                onClose={closeDrawer}
                isAdmin={isAdmin}
                abilities={abilities}
                savingAbility={savingAbility}
                onAbilityChange={(id, patch) => void changeAbility(id, patch)}
                evidence={evidenceFor}
                recommendations={evidence.recommendations}
                plays={evidence.plays}
                onEvidenceChanged={() => void evidence.refresh()}
                candidates={candidates}
                candidatesError={Boolean(candidatesError)}
                onCandidatesChanged={() => void mutateCandidates()}
                onDismissCard={dismissCard}
                sharePath={(item) => (item.href.startsWith("/") ? item.href : APP_ROUTES.intelligencePredictive)}
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
