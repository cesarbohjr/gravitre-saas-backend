"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { intelligenceApi } from "@/lib/api"
import { canonicalAgentsToMapAgents } from "@/lib/intelligence/canonical-agents"
import { ApiError } from "@/lib/fetcher"
import { ensureSelectedOrg } from "@/lib/org-context"
import { readNumber } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { SimulationCard } from "@/components/intelligence/simulation-card"
import { IntelligenceHealthGrid } from "@/components/intelligence/intelligence-health-grid"
import { useWhatMattersNow } from "@/components/intelligence/what-matters-now"
import {
  canonicalLearningsForDisplay,
  canonicalPredictionsToAttentionSignals,
} from "@/lib/intelligence/canonical-attention"
import { useIntelligencePillarsData } from "@/components/intelligence/intelligence-pillars"
import { WhyGravitrePanel, useWhyGravitreEvidence } from "@/components/intelligence/why-gravitre-panel"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import {
  IntelligenceAskCommandSurface,
  IntelligenceShell,
} from "@/components/intelligence/shell"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"
import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import {
  usePublishGravitreAISelection,
  type GravitreAISelectedEntity,
} from "@/components/gravitre/ai-workspace-provider"
import { OverviewLivingMap } from "@/components/intelligence/pages/overview-living-map"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import { IntelligenceFreshnessBar } from "@/components/intelligence/shell/intelligence-freshness-bar"
import { EvidenceRail, InsightRail, IntelligenceJourney } from "@/components/intelligence/journey-rails"
import { buildLensMetrics } from "@/components/intelligence/map/build-lens-metrics"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  BusinessImpactCompact,
  WhatGravitreLearnedSection,
  WhatNeedsAttentionCompact,
} from "@/components/intelligence/map/intelligence-support-sections"
import {
  applyAssistantVisualizationToMapState,
  type AssistantVisualization,
} from "@/lib/intelligence/assistant-visualization"
import {
  resolveCanonicalGraphMapNode,
  type CanonicalGraphNode,
} from "@/lib/intelligence/canonical-graph-topology"
import { parseIntelligenceMapDeepLink } from "@/lib/intelligence/learning-map-focus"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"

const ADVANCED_LINK_GROUPS = [
  {
    heading: "Measure",
    description: "Business reports and predictive ops.",
    links: [SURFACE_COPY.hubLinks.reports, SURFACE_COPY.hubLinks.predictive],
  },
  {
    heading: "Models",
    description: "Registry, built-in catalog, and training.",
    links: [SURFACE_COPY.hubLinks.builtIn, SURFACE_COPY.hubLinks.models],
  },
  {
    heading: "Knowledge",
    description: "Learning hub and org memory.",
    links: [SURFACE_COPY.hubLinks.learning, SURFACE_COPY.hubLinks.memory],
  },
]

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

function selectedEntityFromMapSelection(selection: IntelligenceMapSelection): GravitreAISelectedEntity | null {
  if (!selection) return null
  if (selection.kind === "agent") {
    return { kind: "agent", id: selection.agent.id, label: selection.agent.name }
  }
  if (selection.kind === "department") {
    return {
      kind: "department",
      id: selection.department.id,
      label: selection.department.id,
    }
  }
  if (selection.kind === "signal") {
    const id = String(selection.signal.id ?? selection.signal.title ?? "")
    const label = String(selection.signal.title ?? selection.signal.id ?? "signal")
    return { kind: "signal", id, label }
  }
  if (selection.kind === "satellite") {
    return { kind: selection.node.kind || "entity", id: selection.node.id, label: selection.node.label }
  }
  return { kind: "relationship", id: selection.edgeId, label: selection.label }
}

function IntelligenceCenterInner() {
  const { user } = useAuth()
  const searchParams = useSearchParams()
  const copy = SURFACE_COPY.insights
  const deepLink = useMemo(
    () => parseIntelligenceMapDeepLink(searchParams),
    [searchParams],
  )
  const [activeLens, setActiveLens] = useState<IntelligenceMapLens>(
    deepLink.lens ?? "knows",
  )
  const [mapSelection, setMapSelection] = useState<IntelligenceMapSelection>(null)
  const [mapHighlightIds, setMapHighlightIds] = useState<string[]>([])
  const [mapDimIds, setMapDimIds] = useState<string[]>([])
  const [mapFocusIds, setMapFocusIds] = useState<string[]>([])
  const [composerPendingQuestion, setComposerPendingQuestion] = useState<string | null>(null)
  const [orgReady, setOrgReady] = useState(false)
  const askSelected = useMemo(() => selectedEntityFromMapSelection(mapSelection), [mapSelection])
  usePublishGravitreAISelection(askSelected)

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

  const { data: outcomes, error, mutate } = useSWR(
    user && orgReady ? ["intelligence/outcomes", 7] : null,
    () => intelligenceApi.outcomes({ periodDays: 7 }),
    { revalidateOnFocus: false },
  )
  const { data: trust } = useSWR(
    user && orgReady ? "intelligence/trust-summary" : null,
    () => intelligenceApi.trustSummary({ periodDays: 7 }),
  )
  const { data: simulations } = useSWR(
    user && orgReady ? "intelligence/simulations" : null,
    () => intelligenceApi.simulations(),
  )
  const {
    data: pageContext,
    loadState: snapshotLoadState,
    generatedAt,
    isValidating: snapshotValidating,
    mutate: mutateSnapshot,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user) && orgReady,
    activeLens,
    windowHours: 24,
  })

  const { data: businessSignals, isLoading: legacySignalsLoading } = useWhatMattersNow(
    Boolean(user) && orgReady && !pageContext,
  )
  const { coreState, businessImpact } = useIntelligencePillarsData(
    Boolean(user) && orgReady && !isSnapshotMetricsReady(snapshotLoadState),
  )
  const { data: whyEvidence, isLoading: whyEvidenceLoading } = useWhyGravitreEvidence(
    Boolean(user) && orgReady,
  )

  const mapAgents = useMemo(
    () => canonicalAgentsToMapAgents(pageContext?.snapshot.agents),
    [pageContext?.snapshot.agents],
  )

  const canonicalMetrics = pageContext?.metrics ?? pageContext?.snapshot.metrics

  const lensMetrics = useMemo(
    () =>
      buildLensMetrics({
        knowledgeGraph: null,
        readiness: null,
        modelCatalog: null,
        coreState: coreState.data,
        businessImpact: businessImpact.data,
        outcomesByEvent: (outcomes?.by_event_type as Record<string, number> | undefined) ?? {},
        canonicalMetrics,
        loadState: snapshotLoadState,
      }),
    [coreState.data, businessImpact.data, outcomes, canonicalMetrics, snapshotLoadState],
  )

  const canonicalAttentionSignals = useMemo(
    () =>
      canonicalPredictionsToAttentionSignals(
        pageContext?.snapshot.predictions as Parameters<
          typeof canonicalPredictionsToAttentionSignals
        >[0],
      ),
    [pageContext?.snapshot.predictions],
  )

  const signals = useMemo(() => {
    if (canonicalAttentionSignals.length > 0) return canonicalAttentionSignals
    return (businessSignals?.signals as Record<string, unknown>[] | undefined) ?? []
  }, [canonicalAttentionSignals, businessSignals?.signals])

  const signalsLoading = pageContext ? false : legacySignalsLoading

  const displayLearnings = useMemo(
    () =>
      canonicalLearningsForDisplay(
        pageContext?.snapshot.learnings as Parameters<typeof canonicalLearningsForDisplay>[0],
      ),
    [pageContext?.snapshot.learnings],
  )

  const graphNodeIds = useMemo(() => {
    const ids = new Set<string>()
    for (const node of pageContext?.graph?.nodes ?? []) {
      const id = typeof node.id === "string" ? node.id : null
      if (id) ids.add(id)
    }
    return ids
  }, [pageContext?.graph?.nodes])

  const applyMapVisualization = useCallback(
    (state: ReturnType<typeof applyAssistantVisualizationToMapState>) => {
      if (state.lens) setActiveLens(state.lens)
      setMapHighlightIds(state.highlightNodeIds)
      setMapDimIds(state.dimNodeIds)
      setMapFocusIds(state.focusNodeIds)
      if (state.selection) setMapSelection(state.selection)
      window.scrollTo({ top: 0, behavior: "smooth" })
    },
    [],
  )

  const handleAssistantVisualization = useCallback(
    (visualization: AssistantVisualization) => {
      const state = applyAssistantVisualizationToMapState(visualization, {
        graphNodeIds: graphNodeIds.size > 0 ? graphNodeIds : undefined,
        agents: mapAgents,
        departments: coreState.data?.departments ?? [],
        signals: signals ?? [],
      })
      applyMapVisualization(state)
    },
    [
      applyMapVisualization,
      graphNodeIds,
      mapAgents,
      coreState.data?.departments,
      signals,
    ],
  )

  useEffect(() => {
    if (mapHighlightIds.length === 0 && mapDimIds.length === 0) return
    const timer = window.setTimeout(() => {
      setMapHighlightIds([])
      setMapDimIds([])
      setMapFocusIds([])
    }, 12_000)
    return () => window.clearTimeout(timer)
  }, [mapHighlightIds, mapDimIds])

  useEffect(() => {
    const { focusNodeId, lens } = deepLink
    if (!focusNodeId || !pageContext?.graph?.nodes?.length) return
    if (lens) setActiveLens(lens)
    const viz: AssistantVisualization = {
      lens: lens ?? undefined,
      focusNodeIds: [focusNodeId],
      highlightNodeIds: [focusNodeId],
    }
    const state = applyAssistantVisualizationToMapState(viz, {
      graphNodeIds: graphNodeIds.size > 0 ? graphNodeIds : undefined,
      agents: mapAgents,
      departments: coreState.data?.departments ?? [],
      signals: signals ?? [],
    })
    applyMapVisualization(state)
    const mapNode = resolveCanonicalGraphMapNode(
      focusNodeId,
      {
        nodes: pageContext.graph.nodes as CanonicalGraphNode[],
      },
      mapAgents,
    )
    if (mapNode) {
      setMapSelection({ kind: "satellite", node: mapNode })
    }
  }, [
    deepLink,
    pageContext?.graph,
    graphNodeIds,
    mapAgents,
    coreState.data?.departments,
    signals,
    applyMapVisualization,
  ])

  if (!user) {
    return (
      <AppShell title={copy.title}>
        <EmptyState title="Sign in required" description="Log in to view insights." />
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

  if (error) {
    const isOrgDenied =
      error instanceof ApiError &&
      error.status === 403 &&
      /not a member of the requested organization/i.test(error.message)
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load insights"
          description={
            isOrgDenied
              ? "Your saved workspace no longer matches membership. We cleared it — try again, or pick an organization in Settings."
              : error instanceof ApiError
                ? error.message
                : "Try again in a moment."
          }
          onRetry={() => {
            if (isOrgDenied) {
              void ensureSelectedOrg(true).then(() => mutate())
              return
            }
            mutate()
          }}
        />
      </AppShell>
    )
  }

  const summary = (outcomes?.summary as Record<string, unknown> | undefined) ?? {}
  const totalEvents = readNumber(summary.total_events, 0)
  const avgConfidence = trust?.avg_confidence as number | null | undefined
  const journeyStep: 0 | 1 | 2 = !askSelected ? 0 : askSelected.kind === "relationship" ? 2 : 1
  return (
    <AppShell title={copy.title}>
      <div className="relative bg-[color:var(--g-canvas)]">
        <IntelligenceSectionRedirect />

        <GravitrePageHeader
          family="expert"
          title={copy.title}
          description="How your agents, systems, and knowledge connect. Select anything on the field to see the evidence."
          icon={<NucleoIntelligence className="h-[18px] w-[18px]" />}
          status={
            <IntelligenceFreshnessBar
              loadState={snapshotLoadState}
              generatedAt={generatedAt}
              isValidating={snapshotValidating}
              onRefresh={() => mutateSnapshot()}
              className="justify-start"
            />
          }
          actions={<IntelligenceJourney step={journeyStep} className="hidden md:flex" />}
        >
          <IntelligenceHubTabs active="overview" />
        </GravitrePageHeader>

        {/* Field-primary: insight rail · dominant field · evidence rail */}
        <section className="relative border-b border-divide">
          <div className="relative z-10 mx-auto grid max-w-[1680px] gap-5 px-4 py-4 md:grid-cols-2 md:px-6 md:py-5 xl:grid-cols-[244px_minmax(0,1fr)_264px] xl:gap-6">
            <aside aria-label="Insight" className="order-2 min-w-0 xl:order-1 xl:pt-1">
              <InsightRail
                signals={signals}
                signalsLoading={signalsLoading}
                learnings={displayLearnings}
                onSelectSignal={(signal) => {
                  setMapSelection({ kind: "signal", signal })
                  setActiveLens("predicts")
                }}
              />
            </aside>
            <div className="order-1 min-w-0 md:col-span-2 xl:order-2 xl:col-span-1">
            <IntelligenceShell
              chrome="none"
              activeTab="overview"
              loadState={snapshotLoadState}
              generatedAt={generatedAt}
              isValidating={snapshotValidating}
              onRefresh={() => mutateSnapshot()}
              commandBar={
                <IntelligenceAskCommandSurface
                  enabled={Boolean(user)}
                  pageSuggestedQuestions={pageContext?.suggestedQuestions}
                  onVisualization={handleAssistantVisualization}
                  pendingQuestion={composerPendingQuestion}
                  onPendingQuestionConsumed={() => setComposerPendingQuestion(null)}
                  selected={askSelected}
                />
              }
            >
              <OverviewLivingMap
                activeLens={activeLens}
                onLensChange={(lens) => {
                  setActiveLens(lens)
                  setMapSelection(null)
                  setMapHighlightIds([])
                  setMapDimIds([])
                  setMapFocusIds([])
                }}
                lensMetrics={lensMetrics}
                snapshotLoadState={snapshotLoadState}
                pageContext={pageContext}
                mapAgents={mapAgents}
                signals={signals}
                entityCount={canonicalMetrics?.knowledge?.knownEntities ?? null}
                relationshipCount={canonicalMetrics?.knowledge?.knownRelationships ?? null}
                selection={mapSelection}
                onSelectionChange={setMapSelection}
                highlightNodeIds={mapHighlightIds}
                dimNodeIds={mapDimIds}
                focusNodeIds={mapFocusIds}
                whyEvidence={whyEvidence}
                onAskAbout={(question) => {
                  setComposerPendingQuestion(question)
                  window.scrollTo({ top: 0, behavior: "smooth" })
                }}
                cacheKey={`overview:${activeLens}`}
              />
            </IntelligenceShell>
            </div>
            <aside aria-label="Evidence" className="order-3 min-w-0 xl:pt-1">
              <EvidenceRail
                selected={askSelected}
                totalEvents={totalEvents}
                avgConfidence={avgConfidence}
                entityCount={canonicalMetrics?.knowledge?.knownEntities ?? null}
                relationshipCount={canonicalMetrics?.knowledge?.knownRelationships ?? null}
              />
            </aside>
          </div>
        </section>

        {/* Contextual support — closed until asked; map stays the product */}
        <details className="group/evidence mx-auto max-w-[1600px] px-4 py-6 md:px-6">
          <summary className="cursor-pointer list-none rounded-[4px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
            <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-3">
              <div>
                <h2 className={TYPE.sectionTitle}>Attention, learnings, and impact</h2>
                <p className={cn(TYPE.bodyMuted, "mt-1")}>
                  What needs attention, what Gravitre learned, and the evidence behind it.
                </p>
              </div>
              <span className="text-xs font-medium text-muted-foreground">
                <span className="group-open/evidence:hidden">Show</span>
                <span className="hidden group-open/evidence:inline">Hide</span>
              </span>
            </div>
          </summary>
          <div className="space-y-8 pt-6">
          <WhatNeedsAttentionCompact
            signals={signals}
            isLoading={signalsLoading}
            onSelectSignal={(signal) => {
              setMapSelection({ kind: "signal", signal })
              setActiveLens("predicts")
              window.scrollTo({ top: 0, behavior: "smooth" })
            }}
          />

          <WhatGravitreLearnedSection learnings={displayLearnings} />

          <BusinessImpactCompact totalEvents={totalEvents} avgConfidence={avgConfidence} />

          <WhyGravitrePanel className="relative" data={whyEvidence} isLoading={whyEvidenceLoading} />

          <details className="group/advanced">
            <summary className="cursor-pointer list-none rounded-[4px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
              <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-3">
                <div>
                  <h2 className={TYPE.sectionTitle}>Models, training, and routing</h2>
                  <p className={cn(TYPE.bodyMuted, "mt-1")}>
                    Model health, simulations, and links to the detailed intelligence tools.
                  </p>
                </div>
                <span className="text-xs font-medium text-muted-foreground">
                  <span className="group-open/advanced:hidden">Show</span>
                  <span className="hidden group-open/advanced:inline">Hide</span>
                </span>
              </div>
            </summary>
            <div className="space-y-6 pt-6">
              <IntelligenceHealthGrid orgScopedKey={user ? "intelligence-center" : null} />

              <div className="space-y-6">
                <section>
                  <h3 className={TYPE.sectionTitle}>{SURFACE_COPY.sections.routingTrace}</h3>
                  <p className={cn(TYPE.bodyMuted, "mt-1")}>
                    {SURFACE_COPY.sections.routingTraceHint}
                  </p>
                  <p className={cn(TYPE.meta, "mt-3 border-b border-divide py-3")}>
                    Routing traces appear on each conversation, next to the reply they explain.
                  </p>
                </section>
                <section>
                  <h3 className={TYPE.sectionTitle}>{SURFACE_COPY.sections.latestSimulation}</h3>
                  <p className={cn(TYPE.bodyMuted, "mt-1")}>
                    {SURFACE_COPY.sections.latestSimulationHint}
                  </p>
                  <div className="mt-4">
                    <SimulationCard
                      simulation={(simulations as Record<string, unknown> | undefined) ?? null}
                    />
                  </div>
                </section>
              </div>

              {ADVANCED_LINK_GROUPS.map((group) => (
                <section key={group.heading} aria-labelledby={`adv-${group.heading}`}>
                  <div className="mb-2">
                    <h3 id={`adv-${group.heading}`} className="text-sm font-semibold text-foreground">
                      {group.heading}
                    </h3>
                    <p className={cn(TYPE.bodyMuted, "mt-1")}>{group.description}</p>
                  </div>
                  <nav className="flex flex-col gap-1" aria-label={group.heading}>
                    {group.links.map((link) => (
                      <Link
                        key={link.route}
                        href={link.route}
                        className={cn(
                          TYPE.meta,
                          "py-1.5 underline-offset-4 hover:text-[color:var(--g-text-primary)] hover:underline",
                        )}
                      >
                        {link.title}
                        <span className="ml-2 text-[color:var(--g-text-muted)]">{link.summary}</span>
                      </Link>
                    ))}
                  </nav>
                </section>
              ))}

              <div className="flex flex-wrap gap-2">
                <Button variant="ghost" size="sm" asChild>
                  <Link href={`${APP_ROUTES.learning}#revenue-risk`}>Revenue risk</Link>
                </Button>
                <Button variant="ghost" size="sm" asChild>
                  <Link href={APP_ROUTES.agents}>AI team</Link>
                </Button>
              </div>
            </div>
          </details>
          </div>
        </details>
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
