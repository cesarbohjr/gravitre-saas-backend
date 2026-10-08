"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Illustration } from "@/components/gravitre/illustration"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/fetcher"
import { PAGE_FRAME, TYPE } from "@/lib/design-system"
import { ArrowRight, PlayCircle } from "lucide-react"
import { GravitreEmpty } from "@/components/gravitre/nodus-product"
import { AuthorityLadder } from "@/components/plays/authority-ladder"

type PlayReadiness = {
  dependency_status?: string
  observe_ready?: boolean
  recommend_ready?: boolean
  act_with_approval_ready?: boolean
  act_within_policy_ready?: boolean
  blockers?: string[]
  connector_groups?: Array<{ ready?: boolean }>
}

type PlayItem = {
  play: { key: string; name: string; objective: string; version: string }
  readiness: PlayReadiness
  workflowBindingCount: number
}

type PlaysResponse = { plays: PlayItem[]; count: number }

function readinessLabel(readiness: PlayReadiness): { label: string; tone: "ready" | "setup" | "attention" } {
  if (readiness.act_with_approval_ready) return { label: "Ready to act with approval", tone: "ready" }
  if (readiness.recommend_ready) return { label: "Ready to recommend", tone: "ready" }
  if (readiness.observe_ready) return { label: "Ready to observe", tone: "ready" }
  if ((readiness.blockers?.length ?? 0) > 0) return { label: "Setup required", tone: "setup" }
  return { label: "Needs attention", tone: "attention" }
}

function readinessClasses(tone: "ready" | "setup" | "attention"): string {
  if (tone === "ready") return "border-success/25 bg-success/10 text-success"
  if (tone === "setup") return "border-warning/25 bg-warning/10 text-warning"
  return "border-border bg-muted text-muted-foreground"
}

function setupHref(readiness: PlayReadiness): string {
  const blockers = (readiness.blockers ?? []).join(" ").toLowerCase()
  if (blockers.includes("connector")) return "/connectors"
  if (blockers.includes("workflow")) return "/workflows"
  return "/connectors"
}

export default function PlaysPage() {
  const { data, error, isLoading, mutate } = useSWR<PlaysResponse>("/api/plays", fetcher, {
    refreshInterval: 30_000,
  })
  const plays = data?.plays ?? []
  const readyCount = plays.filter((item) => item.readiness.observe_ready).length

  return (
    <AppShell>
      <div className={PAGE_FRAME} data-composition="operate">
        <GravitrePageHeader
          title="Plays"
          description="Turn business goals into coordinated action across your agents, data, and systems."
          icon={<PlayCircle className="h-5 w-5" />}
          status={plays.length ? <LiveStatus tone={readyCount ? "live" : "idle"}>{readyCount} of {plays.length} ready to observe</LiveStatus> : undefined}
        />

        {error ? (
          <div className="space-y-4">
            <Illustration name="moment-error" width={160} />
            <WorkSectionErrorCard
              title="Could not load plays"
              message={error instanceof Error ? error.message : "Unknown error"}
              onRetry={() => void mutate()}
            />
          </div>
        ) : isLoading ? (
          <div className="divide-y divide-divide border-y border-divide">
            {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-24 w-full rounded-none" />)}
          </div>
        ) : plays.length === 0 ? (
          <GravitreEmpty
            illustration="moment-welcome"
            title="No plays in this workspace"
            hint="Plays appear here when the catalog returns them for your organization. Nothing is invented when the list is empty."
          />
        ) : (
          <div className="divide-y divide-divide border-y border-divide">
            {plays.map(({ play, readiness, workflowBindingCount }) => {
              const state = readinessLabel(readiness)
              const connectorGroups = readiness.connector_groups ?? []
              const connectorReady = connectorGroups.filter((group) => group.ready).length
              return (
                <article key={play.key} className="group relative flex flex-col gap-4 py-5 md:flex-row md:items-start md:gap-8">
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className={TYPE.eyebrow}>Outcome play</p>
                      {state.tone !== "ready" ? <Badge variant="outline" className={readinessClasses(state.tone)}>{state.label}</Badge> : null}
                    </div>
                    <h2 className="text-base font-semibold text-foreground text-balance">
                      <Link href={`/plays/${play.key}`} className="rounded-sm after:absolute after:inset-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        {play.name}
                      </Link>
                    </h2>
                    <p className="text-sm leading-6 text-muted-foreground text-pretty">{play.objective}</p>
                    <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm">
                      <p>
                        <span className="text-muted-foreground">Data connections </span>
                        <span className="font-medium text-foreground">{connectorReady} of {connectorGroups.length} ready</span>
                      </p>
                      <p>
                        <span className="text-muted-foreground">Workflows </span>
                        <span className="font-medium text-foreground">{workflowBindingCount} linked</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-col gap-3 md:w-72 md:shrink-0">
                    <AuthorityLadder readiness={readiness} />
                    <div className="relative z-10 flex flex-wrap items-center gap-2">
                      {!readiness.observe_ready ? (
                        <Button variant="outline" size="sm" className="min-h-11" asChild>
                          <Link href={setupHref(readiness)}>Finish setup</Link>
                        </Button>
                      ) : null}
                      <Button variant="ghost" size="sm" className="min-h-11 gap-1.5 px-2 text-foreground" asChild>
                        <Link href={`/plays/${play.key}`} aria-label={`View ${play.name}`}>
                          View play <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
    </AppShell>
  )
}
