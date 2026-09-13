"use client"

import { Suspense, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { agentsApi, intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { readNumber } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { SimulationCard } from "@/components/intelligence/simulation-card"
import { IntelligenceHealthGrid } from "@/components/intelligence/intelligence-health-grid"
import { GibeHonestyStrip } from "@/components/intelligence/gibe-honesty-strip"
import { TrainingReadinessStrip } from "@/components/intelligence/training-readiness-strip"
import { useWhatMattersNow } from "@/components/intelligence/what-matters-now"
import { AskGravitreComposer, useAskGravitreSuggestions } from "@/components/intelligence/ask-gravitre-composer"
import { useIntelligencePillarsData } from "@/components/intelligence/intelligence-pillars"
import { WhyGravitrePanel, useWhyGravitreEvidence } from "@/components/intelligence/why-gravitre-panel"
import { LivingMineralField } from "@/components/gravitre/visual"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import {
  IntelligenceMap,
  type IntelligenceMapSelection,
} from "@/components/intelligence/map/intelligence-map"
import { IntelligenceLensBar } from "@/components/intelligence/map/intelligence-lens-bar"
import { IntelligenceMapContextPanel } from "@/components/intelligence/map/intelligence-map-context-panel"
import { buildLensMetrics } from "@/components/intelligence/map/build-lens-metrics"
import type { IntelligenceMapLens } from "@/components/intelligence/map/intelligence-map-lens"
import {
  BusinessImpactCompact,
  WhatGravitreLearnedSection,
  WhatNeedsAttentionCompact,
} from "@/components/intelligence/map/intelligence-support-sections"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  Cpu,
  Database,
  Heartbeat,
  Sparkle,
} from "@phosphor-icons/react"

const ADVANCED_LINK_GROUPS = [
  {
    heading: "Measure",
    description: "Operational health, reports, and predictive ops.",
    links: [
      { ...SURFACE_COPY.hubLinks.operationalHealth, icon: Heartbeat },
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
  const copy = SURFACE_COPY.insights
  const [activeLens, setActiveLens] = useState<IntelligenceMapLens>("knows")
  const [mapSelection, setMapSelection] = useState<IntelligenceMapSelection>(null)

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
  const { data: modelCatalog } = useSWR(user ? "intelligence/model-catalog" : null, () =>
    intelligenceApi.modelCatalog(),
  )
  const { data: readiness, isLoading: readinessLoading } = useSWR(
    user ? "intelligence/training-readiness" : null,
    () => intelligenceApi.trainingReadiness(),
    { revalidateOnFocus: false },
  )
  const { data: agentsResponse } = useSWR(user ? "intelligence/map/agents" : null, () =>
    agentsApi.list(),
  )

  const { data: businessSignals, isLoading: signalsLoading } = useWhatMattersNow(Boolean(user))
  const { data: dailyBriefing } = useAskGravitreSuggestions(Boolean(user))
  const { knowledgeGraph, coreState, businessImpact } = useIntelligencePillarsData(Boolean(user))
  const { data: whyEvidence, isLoading: whyEvidenceLoading } = useWhyGravitreEvidence(Boolean(user))

  const lensMetrics = useMemo(
    () =>
      buildLensMetrics({
        knowledgeGraph: knowledgeGraph.data,
        readiness,
        modelCatalog,
        coreState: coreState.data,
        businessImpact: businessImpact.data,
        outcomesByEvent: (outcomes?.by_event_type as Record<string, number> | undefined) ?? {},
      }),
    [knowledgeGraph.data, readiness, modelCatalog, coreState.data, businessImpact.data, outcomes],
  )

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
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const hasRuntimeRows = Object.keys(orgTraining).length > 0
  const signals = businessSignals?.signals as Record<string, unknown>[] | undefined

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
              eyebrow="GIBE"
              title={copy.title}
              description="One shared intelligence coordinating your business — explore the live map, then inspect evidence below."
              icon={<NucleoIntelligence className="h-5 w-5" />}
            />
            <IntelligenceHubTabs active="overview" className="flex-wrap" />

            <AskGravitreComposer
              variant="map"
              suggestions={dailyBriefing?.suggestions}
            />

            <div className="flex min-h-[52vh] flex-col gap-4 lg:flex-row">
              <IntelligenceMap
                lens={activeLens}
                signals={signals}
                agents={agentsResponse?.agents}
                entityTypes={knowledgeGraph.data?.entity_types}
                readiness={readiness}
                orgTraining={modelCatalog?.orgTrainingStatus}
                entityCount={knowledgeGraph.data?.entity_count}
                relationshipCount={knowledgeGraph.data?.relationship_count}
                selection={mapSelection}
                onSelectionChange={setMapSelection}
                className="min-h-[48vh] lg:min-h-[52vh]"
              />
              <IntelligenceMapContextPanel
                selection={mapSelection}
                className="w-full shrink-0 lg:w-80"
              />
            </div>

            <IntelligenceLensBar
              activeLens={activeLens}
              onLensChange={(lens) => {
                setActiveLens(lens)
                setMapSelection(null)
              }}
              metrics={lensMetrics}
            />
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

          <WhatGravitreLearnedSection />

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
              <GibeHonestyStrip orgTraining={hasRuntimeRows ? orgTraining : null} />
              <TrainingReadinessStrip readiness={readiness} loading={readinessLoading} />
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
