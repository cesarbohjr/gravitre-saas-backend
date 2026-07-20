"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { RecommendationExplanation } from "@/components/intelligence/recommendation-explanation"
import { HeuristicSuggestionCards } from "@/components/intelligence/heuristic-suggestion-cards"
import { SimulationCard } from "@/components/intelligence/simulation-card"
import { IntelligenceTrace } from "@/components/intelligence/intelligence-trace"
import { IntelligenceHealthGrid } from "@/components/intelligence/intelligence-health-grid"
import { Badge } from "@/components/ui/badge"
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  Cpu,
  Robot,
  Sparkle,
} from "@phosphor-icons/react"

const LINKS = [
  { ...SURFACE_COPY.hubLinks.agents, icon: Robot },
  { ...SURFACE_COPY.hubLinks.builtIn, icon: Cpu },
  { ...SURFACE_COPY.hubLinks.predictive, icon: ChartLineUp },
  { ...SURFACE_COPY.hubLinks.memory, icon: Brain },
  { ...SURFACE_COPY.hubLinks.reports, icon: ChartLineUp },
]

export default function IntelligenceCenterPage() {
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
  const runtimeEntries = Object.entries(orgTraining).slice(0, 6)
  const heuristicRuntimeCount = runtimeEntries.filter(
    ([, row]) => readString(row?.runtime_status, "") === "heuristic",
  ).length
  const trainedRuntimeCount = runtimeEntries.filter(
    ([, row]) =>
      readString(row?.runtime_status, "") === "trained" || Boolean(row?.artifact_loaded),
  ).length

  return (
    <AppShell title={copy.title}>
      <div className="space-y-6 p-4 md:p-6">
        <PageHeader title={copy.title} description={copy.description} />

        {runtimeEntries.length > 0 ? (
          <section className="rounded-2xl border border-border/70 bg-card p-4 md:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-foreground">Model runtime honesty</h2>
                <p className="mt-1 text-sm text-muted-foreground text-pretty">
                  Whether each model is running a loaded artifact or a heuristic fallback — not the
                  catalog TRAINED label alone.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="border-amber-500/30 bg-amber-500/5">
                  {heuristicRuntimeCount} heuristic
                </Badge>
                <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/5">
                  {trainedRuntimeCount} artifact-loaded
                </Badge>
              </div>
            </div>
            <ul className="mt-3 flex flex-wrap gap-2">
              {runtimeEntries.map(([name, row]) => {
                const status = readString(row?.runtime_status, "unknown")
                const isHeuristic = status === "heuristic"
                return (
                  <li key={name}>
                    <Badge
                      variant="outline"
                      className={
                        isHeuristic
                          ? "border-amber-500/30 bg-amber-500/5 text-amber-950 dark:text-amber-100"
                          : "border-sky-500/30 bg-sky-500/5"
                      }
                      title={
                        row?.artifact_loaded
                          ? "Trained artifact loaded at runtime"
                          : "Heuristic path — no trained artifact loaded"
                      }
                    >
                      {name.replace(/_/g, " ")} · {status.replace(/_/g, " ")}
                    </Badge>
                  </li>
                )
              })}
            </ul>
            <div className="mt-3">
              <Button variant="link" size="sm" className="h-auto px-0" asChild>
                <Link href={APP_ROUTES.intelligenceModelsPath}>View all models</Link>
              </Button>
            </div>
          </section>
        ) : null}

        {isLoading && !outcomes ? (
          <p className="text-sm text-muted-foreground">Loading insights…</p>
        ) : totalEvents === 0 ? (
          <EmptyState
            variant="ai"
            iconSlot={<Sparkle className="h-8 w-8 text-violet-500" weight="duotone" aria-hidden />}
            title={copy.emptyTitle}
            description={copy.emptyDescription}
          />
        ) : (
          <StatsGrid columns={4}>
            <StatCard label={SURFACE_COPY.stats.outcomeEvents} value={totalEvents} variant="info" />
            <StatCard
              label={SURFACE_COPY.stats.avgConfidence}
              value={avgConfidence != null ? formatPercent(avgConfidence) : "—"}
              variant="success"
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
          <section className="rounded-2xl border border-border/70 bg-card p-5">
            <h2 className="text-base font-semibold text-foreground">{SURFACE_COPY.sections.routingTrace}</h2>
            <p className="mt-1 text-sm text-muted-foreground text-pretty">
              {SURFACE_COPY.sections.routingTraceHint}
            </p>
            <div className="mt-4">
              <IntelligenceTrace
                stages={[
                  {
                    label: "Task classified",
                    detail: readString(outcomes?.scopeNote, "Org-scoped classification"),
                    status: "ok",
                  },
                  {
                    label: "Context assembled",
                    detail: "Retrieval and connector signals merged for the request.",
                    status: "ok",
                  },
                  {
                    label: "Risk evaluated",
                    detail: `${readNumber(trust?.advisory_only_rate, 0) > 0 ? "Some actions require approval." : "Advisory-only routing active."}`,
                    status: "pending",
                  },
                ]}
              />
            </div>
          </section>
          <section className="rounded-2xl border border-border/70 bg-card p-5">
            <h2 className="text-base font-semibold text-foreground">{SURFACE_COPY.sections.latestSimulation}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{SURFACE_COPY.sections.latestSimulationHint}</p>
            <div className="mt-4">
              <SimulationCard simulation={(simulations as Record<string, unknown> | undefined) ?? null} />
            </div>
          </section>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {LINKS.map((link) => {
            const Icon = link.icon
            return (
              <Link
                key={link.route}
                href={link.route}
                className="group rounded-2xl border border-border/70 bg-card p-5 transition-colors hover:border-primary/30 hover:bg-card/80"
              >
                <div className="flex items-start gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" weight="duotone" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="font-semibold text-foreground">{link.title}</span>
                    <p className="mt-1 text-sm text-muted-foreground text-pretty">{link.summary}</p>
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

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={APP_ROUTES.learning}>{SURFACE_COPY.learning.title}</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
