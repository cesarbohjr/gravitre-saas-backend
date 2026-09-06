"use client"

import { Suspense, useEffect } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { formatPercent, readNumber } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { RecommendationExplanation } from "@/components/intelligence/recommendation-explanation"
import { HeuristicSuggestionCards } from "@/components/intelligence/heuristic-suggestion-cards"
import { SimulationCard } from "@/components/intelligence/simulation-card"
import { IntelligenceHealthGrid } from "@/components/intelligence/intelligence-health-grid"
import { GibeHonestyStrip } from "@/components/intelligence/gibe-honesty-strip"
import { LivingMineralField } from "@/components/gravitre/visual"
import { ConfidenceBadge } from "@/components/intelligence/confidence-badge"
import { StatsSkeleton } from "@/components/gravitre/loading-state"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { TYPE, RADIUS } from "@/lib/design-system"
import { ESTIMATED_CONFIDENCE_LABEL } from "@/lib/outcome-labels"
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

/**
 * The seven destinations answer three different questions, so they're grouped
 * rather than dumped as one flat 7-card grid where everything competes equally:
 * how is it performing, what models drive it, and what does it know.
 */
const LINK_GROUPS = [
  {
    heading: "Measure",
    description: "How the system is performing right now.",
    links: [
      { ...SURFACE_COPY.hubLinks.operationalHealth, icon: Heartbeat },
      { ...SURFACE_COPY.hubLinks.reports, icon: ChartLineUp },
      { ...SURFACE_COPY.hubLinks.predictive, icon: ChartLineUp },
    ],
  },
  {
    heading: "Models",
    description: "What drives the predictions and how they're managed.",
    links: [
      { ...SURFACE_COPY.hubLinks.builtIn, icon: Cpu },
      { ...SURFACE_COPY.hubLinks.models, icon: Database },
    ],
  },
  {
    heading: "Knowledge",
    description: "What the system has learned and retained.",
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
  const { data: outcomes, error, mutate, isLoading } = useSWR(
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
  // Module C: surface heuristic vs trained runtime on the hub (not only admin models).
  const { data: modelCatalog } = useSWR(user ? "intelligence/model-catalog" : null, () =>
    intelligenceApi.modelCatalog(),
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
  const byEvent = (outcomes?.by_event_type as Record<string, number> | undefined) ?? {}
  const totalEvents = readNumber(summary.total_events, 0)
  const avgConfidence = trust?.avg_confidence as number | null | undefined
  const trustRecord = trust as Record<string, unknown> | undefined
  const confidenceIsEstimate = Boolean(
    trustRecord?.confidence_is_estimate ?? trustRecord?.confidenceIsEstimate,
  )
  const orgTraining = modelCatalog?.orgTrainingStatus ?? {}
  const hasRuntimeRows = Object.keys(orgTraining).length > 0

  return (
    <AppShell title={copy.title}>
      <div className="relative space-y-6 bg-[color:var(--g-canvas)] p-4 md:p-6">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-56 overflow-hidden">
          <LivingMineralField intensity="section" className="opacity-80" />
        </div>
        <IntelligenceSectionRedirect />
        <PageHeader
          className="relative border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/80 backdrop-blur-sm"
          eyebrow="GIBE"
          title={copy.title}
          description={copy.description}
          icon={NucleoIntelligence}
        />

        {/* Always show Module C strip — empty state is honest when catalog has no rows */}
        <div className="relative">
          <GibeHonestyStrip orgTraining={hasRuntimeRows ? orgTraining : null} />
        </div>

        {isLoading && !outcomes ? (
          <StatsSkeleton count={4} />
        ) : totalEvents === 0 ? (
          <EmptyState
            variant="ai"
            iconSlot={<Sparkle className="h-8 w-8 text-primary" weight="duotone" aria-hidden />}
            title={copy.emptyTitle}
            description={copy.emptyDescription}
          />
        ) : (
          <StatsGrid columns={4}>
            <StatCard label={SURFACE_COPY.stats.outcomeEvents} value={totalEvents} variant="info" />
            <StatCard
              label={
                confidenceIsEstimate
                  ? ESTIMATED_CONFIDENCE_LABEL
                  : SURFACE_COPY.stats.avgConfidence
              }
              value={
                avgConfidence != null ? (
                  <span className="inline-flex flex-col items-center gap-1">
                    <span>{formatPercent(avgConfidence)}</span>
                    <ConfidenceBadge
                      score={avgConfidence}
                      isEstimate={confidenceIsEstimate}
                      showScore={false}
                      className="text-[10px] normal-case tracking-normal"
                    />
                  </span>
                ) : (
                  "—"
                )
              }
              variant={confidenceIsEstimate ? "warning" : "success"}
            />
            <StatCard
              label={SURFACE_COPY.stats.recommendationsCreated}
              value={readNumber(byEvent.recommendation_created, 0)}
            />
            <StatCard
              label={SURFACE_COPY.stats.recommendationsRejected}
              value={readNumber(byEvent.recommendation_rejected, 0)}
              variant="warning"
            />
          </StatsGrid>
        )}

        {avgConfidence == null && !isLoading ? (
          <p className={cn(TYPE.meta, "rounded-lg border border-dashed border-border bg-muted/30 px-3 py-2", RADIUS.tile)}>
            Avg confidence not yet available for this period — shown as — rather than a fabricated score.
          </p>
        ) : null}

        <RecommendationExplanation
          summary={SURFACE_COPY.sections.recommendationSummary}
          confidence={typeof avgConfidence === "number" ? avgConfidence : null}
          isEstimate={confidenceIsEstimate}
          advisoryOnly
          sources={[{ type: "optimization_suggestions", label: "Org optimization signals" }]}
        />

        <HeuristicSuggestionCards />

        <IntelligenceHealthGrid orgScopedKey={user ? "intelligence-center" : null} />

        <div className="grid gap-4 lg:grid-cols-2">
          <section className={cn("border border-border bg-card p-5 shadow-sm", RADIUS.panel)}>
            <h2 className={TYPE.sectionTitle}>{SURFACE_COPY.sections.routingTrace}</h2>
            <p className={cn(TYPE.bodyMuted, "mt-1")}>
              {SURFACE_COPY.sections.routingTraceHint}
            </p>
            <div
              className={cn(
                "mt-4 border border-dashed border-border bg-muted/30 px-4 py-6 text-center",
                RADIUS.card,
              )}
            >
              <p className={TYPE.cardTitle}>No live routing trace on this hub</p>
              <p className={cn(TYPE.meta, "mt-1")}>
                Per-turn traces appear on chat / decision surfaces with real SSE metadata — this page
                does not invent “ok” stage chips.
              </p>
            </div>
          </section>
          <section className={cn("border border-border bg-card p-5 shadow-sm", RADIUS.panel)}>
            <h2 className={TYPE.sectionTitle}>{SURFACE_COPY.sections.latestSimulation}</h2>
            <p className={cn(TYPE.bodyMuted, "mt-1")}>{SURFACE_COPY.sections.latestSimulationHint}</p>
            <div className="mt-4">
              <SimulationCard simulation={(simulations as Record<string, unknown> | undefined) ?? null} />
            </div>
          </section>
        </div>

        <div className="space-y-6 border-t border-border pt-6">
          {LINK_GROUPS.map((group) => (
            <section key={group.heading} aria-labelledby={`links-${group.heading}`}>
              <div className="mb-3">
                <h2 id={`links-${group.heading}`} className={TYPE.eyebrow}>
                  {group.heading}
                </h2>
                <p className={cn(TYPE.bodyMuted, "mt-1")}>{group.description}</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                {group.links.map((link) => {
                  const LinkIcon = link.icon
                  return (
                    <Link
                      key={link.route}
                      href={link.route}
                      className={cn(
                        "group border border-border bg-card p-5 shadow-sm transition-colors hover:border-primary/30 hover:bg-accent/50",
                        RADIUS.panel,
                      )}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={cn(
                            "flex h-10 w-10 shrink-0 items-center justify-center bg-primary/10 text-primary",
                            RADIUS.tile,
                          )}
                        >
                          <LinkIcon className="h-5 w-5" weight="duotone" aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className={TYPE.cardTitle}>{link.title}</span>
                          <p className={cn(TYPE.bodyMuted, "mt-1")}>{link.summary}</p>
                        </span>
                        <ArrowRight
                          className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                          aria-hidden
                        />
                      </div>
                    </Link>
                  )
                })}
              </div>
            </section>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-6">
          <span className={TYPE.eyebrow}>Jump to</span>
          <Button variant="outline" size="sm" asChild>
            <Link href={`${APP_ROUTES.learning}#revenue-risk`}>Revenue risk</Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={APP_ROUTES.agents}>Agents hub</Link>
          </Button>
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
