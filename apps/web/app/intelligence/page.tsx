"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState, ErrorState } from "@/components/gravitre/empty-state"
import { PageHeader, StatCard, StatsGrid } from "@/components/gravitre/page-header"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { intelligenceApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { formatPercent, readNumber, readString } from "@/lib/intelligence/helpers"
import { RecommendationExplanation } from "@/components/intelligence/recommendation-explanation"
import { SimulationCard } from "@/components/intelligence/simulation-card"
import { IntelligenceTrace } from "@/components/intelligence/intelligence-trace"
import {
  ArrowRight,
  Brain,
  ChartLineUp,
  Cpu,
  Robot,
  Sparkle,
} from "@phosphor-icons/react"

const LINKS = [
  {
    href: "/intelligence/agents",
    title: "Agent profiles",
    summary: "Health, performance, learning, and outcomes per agent.",
    icon: Robot,
  },
  {
    href: "/intelligence/models",
    title: "Model intelligence",
    summary: "Catalog status, training readiness, and outcome scores.",
    icon: Cpu,
  },
  {
    href: "/intelligence/memory",
    title: "Organizational memory",
    summary: "Promoted memories, auto-promotions, and knowledge graph lens.",
    icon: Brain,
  },
  {
    href: "/intelligence/reports",
    title: "Executive reports",
    summary: "ROI metrics and department scorecards.",
    icon: ChartLineUp,
  },
]

export default function IntelligenceCenterPage() {
  const { user } = useAuth()
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

  if (!user) {
    return (
      <AppShell title="Intelligence Center">
        <EmptyState title="Sign in required" description="Log in to view intelligence visibility." />
      </AppShell>
    )
  }

  if (error) {
    return (
      <AppShell title="Intelligence Center">
        <ErrorState
          title="Unable to load intelligence center"
          description={error instanceof ApiError ? error.message : "Please try again."}
          onRetry={() => mutate()}
        />
      </AppShell>
    )
  }

  const summary = (outcomes?.summary as Record<string, unknown> | undefined) ?? {}
  const byEvent = (outcomes?.by_event_type as Record<string, number> | undefined) ?? {}
  const totalEvents = readNumber(summary.total_events, 0)
  const avgConfidence = trust?.avg_confidence as number | null | undefined

  return (
    <AppShell title="Intelligence Center">
      <div className="space-y-6 p-4 md:p-6">
        <PageHeader
          title="Intelligence Center"
          description="See what Gravitre knows, why recommendations were made, and how confident the system is — without exposing internal chain-of-thought."
        />

        {isLoading && !outcomes ? (
          <p className="text-sm text-muted-foreground">Loading intelligence snapshot…</p>
        ) : totalEvents === 0 ? (
          <EmptyState
            variant="ai"
            iconSlot={<Sparkle className="h-8 w-8 text-violet-500" weight="duotone" aria-hidden />}
            title="Intelligence profile is building"
            description="Outcome events, recommendations, and trust signals appear here as agents complete work with measurable results."
          />
        ) : (
          <StatsGrid columns={4}>
            <StatCard label="Outcome events (7d)" value={totalEvents} variant="info" />
            <StatCard
              label="Avg confidence"
              value={avgConfidence != null ? formatPercent(avgConfidence) : "—"}
              variant="success"
            />
            <StatCard
              label="Recommendations created"
              value={readNumber(byEvent.recommendation_created, 0)}
            />
            <StatCard
              label="Recommendations rejected"
              value={readNumber(byEvent.recommendation_rejected, 0)}
              variant="warning"
            />
          </StatsGrid>
        )}

        <RecommendationExplanation
          summary="Recommendations combine org signals, retrieval quality, and model routing. Each suggestion stays advisory until a human approves or rejects it."
          confidence={typeof avgConfidence === "number" ? avgConfidence : null}
          advisoryOnly
          sources={[{ type: "optimization_suggestions", label: "Org optimization signals" }]}
        />

        <div className="grid gap-4 lg:grid-cols-2">
          <section className="rounded-2xl border border-border/70 bg-card p-5">
            <h2 className="text-base font-semibold text-foreground">Routing trace (safe summary)</h2>
            <p className="mt-1 text-sm text-muted-foreground text-pretty">
              High-level stages only — no raw prompts or chain-of-thought.
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
            <h2 className="text-base font-semibold text-foreground">Latest simulation</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Pre-execution estimates from historical evidence — never fabricated.
            </p>
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
                key={link.href}
                href={link.href}
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
            <Link href="/admin/intelligence">Org Learning admin</Link>
          </Button>
        </div>
      </div>
    </AppShell>
  )
}
