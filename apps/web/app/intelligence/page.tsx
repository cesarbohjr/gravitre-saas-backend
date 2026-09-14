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
import { LivingMineralField } from "@/components/gravitre/visual"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import {
  IntelligenceAskCommandSurface,
  IntelligenceShell,
} from "@/components/intelligence/shell"
import { useIntelligenceSnapshot } from "@/lib/intelligence/use-intelligence-snapshot"
import { isSnapshotMetricsReady } from "@/lib/intelligence/snapshot-state"
import type { IntelligenceMapSelection } from "@/components/intelligence/map/intelligence-map"
import { OverviewLivingMap } from "@/components/intelligence/pages/overview-living-map"
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
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  Cpu,
  Database,
  Sparkle,
} from "@phosphor-icons/react"

const ADVANCED_LINK_GROUPS = [
  {
    heading: "Measure",
    description: "Business reports and predictive ops.",
    links: [
      { ...SURFACE_COPY.hubLinks.reports, icon: ChartLineUp },
      { ...SURFACE_COPY.hubLinks.predictive, icon: ChartLineUp },
    ],
  },
  {
    heading: "Models",
    description: "Registry, built-in catalog, and training.",
    links: [
      { ...SURFACE_COPY.hubLinks.builtIn, icon: Cpu },
      { ...SURFACE_COPY.hubLinks.models, icon: Database },
    ],
  },
  {
    heading: "Knowledge",
    description: "Learning hub and org memory.",
    links: [
      { ...SURFACE_COPY.hubLinks.learning, icon: Sparkle },
      { ...SURFACE_COPY.hubLinks.memory, icon: Brain },
    ],
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

  const { data: outcomes, error, mutate } = useSWR(
    user ? ["intelligence/outcomes", 7] : null,
    () => intelligenceApi.outcomes({ periodDays: 7 }),
    { revalidateOnFocus: false },
  )
  const { data: trust } = useSWR(user ? "intelligence/trust-summary" : null, () =>
    intelligenceApi.trustSummary({ periodDays: 7 }),
  )
  const { data: simulations } = useSWR(user ? "intelligence/simulations" : null, () =>
    intelligenceApi.simulations(),
  )
  const {
    data: pageContext,
    loadState: snapshotLoadState,
    generatedAt,
    isValidating: snapshotValidating,
    mutate: mutateSnapshot,
  } = useIntelligenceSnapshot({
    enabled: Boolean(user),
    activeLens,
    windowHours: 24,
  })

  const { data: businessSignals, isLoading: legacySignalsLoading } = useWhatMattersNow(
    Boolean(user) && !pageContext,
  )
  const { coreState, businessImpact } = useIntelligencePillarsData(
    Boolean(user) && !isSnapshotMetricsReady(snapshotLoadState),
  )
  const { data: whyEvidence, isLoading: whyEvidenceLoading } = useWhyGravitreEvidence(Boolean(user))

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

  if (error) {
    return (
      <AppShell title={copy.title}>
        <ErrorState
          title="Unable to load insights"
          description={error instanceof ApiError ? error.message : "Try again in a moment."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const summary = (outcomes?.summary as Record<string, unknown> | undefined) ?? {}
  const totalEvents = readNumber(summary.total_events, 0)
  const avgConfidence = trust?.avg_confidence as number | null | undefined
  return (
    <AppShell title={copy.title}>
      <div className="relative bg-[color:var(--g-canvas)]">
        <IntelligenceSectionRedirect />

        {/* Dominant map zone — the product, not a card among cards */}
        <section className="relative border-b border-divide">
          <div className="pointer-events-none absolute inset-0 overflow-hidden">
            <LivingMineralField intensity="section" className="opacity-90" />
          </div>
          <div className="relative z-10 mx-auto max-w-[1600px] space-y-4 px-4 py-4 md:px-6 md:py-6">
            <GravitrePageHeader
              className="border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/75 backdrop-blur-sm"
              eyebrow="Intelligence"
              title={copy.title}
              description="One shared intelligence coordinating your business — explore the live map, then inspect evidence below."
              icon={<NucleoIntelligence className="h-5 w-5" />}
            />

            <IntelligenceShell
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
        </section>

        {/* Contextual support — subordinate to the map */}
        <div className="mx-auto max-w-[1600px] space-y-8 px-4 py-8 md:px-6">
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

          <details className="group rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)]">
            <summary className="cursor-pointer list-none px-5 py-4 marker:content-none">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={TYPE.eyebrow}>Advanced</p>
                  <h2 className={TYPE.sectionTitle}>Models, training, routing, and deep tools</h2>
                  <p className={cn(TYPE.bodyMuted, "mt-1")}>
                    Everything that powered the old dashboard layout — still here, no longer the
                    primary experience.
                  </p>
                </div>
                <span className="text-xs text-muted-foreground group-open:rotate-180">▼</span>
              </div>
            </summary>
            <div className="space-y-6 border-t border-divide px-5 py-5">
              <IntelligenceHealthGrid orgScopedKey={user ? "intelligence-center" : null} />

              <div className="grid gap-[var(--np-kpi-gap)] lg:grid-cols-2">
                <section className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]/50 p-5">
                  <h3 className={TYPE.sectionTitle}>{SURFACE_COPY.sections.routingTrace}</h3>
                  <p className={cn(TYPE.bodyMuted, "mt-1")}>
                    {SURFACE_COPY.sections.routingTraceHint}
                  </p>
                  <div className="mt-4 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)] px-4 py-6 text-center">
                    <p className={TYPE.cardTitle}>No live routing trace on this hub</p>
                    <p className={cn(TYPE.meta, "mt-1")}>
                      Per-turn traces appear on chat surfaces with real SSE metadata.
                    </p>
                  </div>
                </section>
                <section className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-2)]/50 p-5">
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
                  <div className="mb-3">
                    <h3 id={`adv-${group.heading}`} className={TYPE.eyebrow}>
                      {group.heading}
                    </h3>
                    <p className={cn(TYPE.bodyMuted, "mt-1")}>{group.description}</p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    {group.links.map((link) => {
                      const LinkIcon = link.icon
                      return (
                        <Link
                          key={link.route}
                          href={link.route}
                          className="group rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-4 transition-colors hover:border-[color:var(--g-brand-border)]"
                        >
                          <div className="flex items-start gap-3">
                            <LinkIcon className="mt-0.5 h-5 w-5 shrink-0 text-[color:var(--g-intelligence)]" />
                            <span className="min-w-0 flex-1">
                              <span className={TYPE.cardTitle}>{link.title}</span>
                              <p className={cn(TYPE.meta, "mt-1")}>{link.summary}</p>
                            </span>
                            <ArrowRight className="h-4 w-4 shrink-0 opacity-50 group-hover:translate-x-0.5" />
                          </div>
                        </Link>
                      )
                    })}
                  </div>
                </section>
              ))}

              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" asChild>
                  <Link href={`${APP_ROUTES.learning}#revenue-risk`}>Revenue risk</Link>
                </Button>
                <Button variant="outline" size="sm" asChild>
                  <Link href={APP_ROUTES.agents}>Agents hub</Link>
                </Button>
              </div>
            </div>
          </details>
        </div>
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
