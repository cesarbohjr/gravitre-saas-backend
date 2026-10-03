"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader, LiveStatus } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { fetcher } from "@/lib/fetcher"
import { PAGE_FRAME } from "@/lib/design-system"
import { ArrowRight, PlayCircle } from "lucide-react"

type PlayReadiness = {
  dependency_status?: string
  observe_ready?: boolean
  recommend_ready?: boolean
  act_with_approval_ready?: boolean
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
      <div className={PAGE_FRAME} data-composition="discover">
        <GravitrePageHeader
          title="Plays"
          description="Turn business goals into coordinated action across your agents, data, and systems."
          icon={<PlayCircle className="h-5 w-5" />}
          status={plays.length ? <LiveStatus tone={readyCount ? "live" : "idle"}>{readyCount} of {plays.length} ready to observe</LiveStatus> : undefined}
        />

        {error ? (
          <WorkSectionErrorCard
            title="Could not load plays"
            message={error instanceof Error ? error.message : "Unknown error"}
            onRetry={() => void mutate()}
          />
        ) : isLoading ? (
          <div className="grid gap-4 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-64 rounded-[10px]" />)}
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            {plays.map(({ play, readiness, workflowBindingCount }) => {
              const state = readinessLabel(readiness)
              const connectorGroups = readiness.connector_groups ?? []
              const connectorReady = connectorGroups.filter((group) => group.ready).length
              return (
                <article key={play.key} className="group flex min-h-64 flex-col rounded-[10px] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)] transition-colors hover:border-[color:var(--g-emerald)]/25">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-medium text-[color:var(--g-emerald-deep)]">Outcome play</p>
                      <h2 className="mt-1 text-lg font-semibold text-foreground">{play.name}</h2>
                    </div>
                    <Badge variant="outline" className={readinessClasses(state.tone)}>{state.label}</Badge>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">{play.objective}</p>
                  <div className="mt-5 grid grid-cols-2 gap-3 border-y border-divide py-3 text-sm">
                    <div>
                      <p className="text-xs text-muted-foreground">Data connections</p>
                      <p className="mt-1 font-medium text-foreground">{connectorReady} of {connectorGroups.length} ready</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">Workflows</p>
                      <p className="mt-1 font-medium text-foreground">{workflowBindingCount} linked</p>
                    </div>
                  </div>
                  <div className="mt-auto flex items-center justify-between gap-2 pt-5">
                    {!readiness.observe_ready ? (
                      <Button variant="outline" size="sm" asChild>
                        <Link href={setupHref(readiness)}>Finish setup</Link>
                      </Button>
                    ) : <span className="text-xs text-muted-foreground">Ready with your workspace</span>}
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/plays/${play.key}`}>View play <ArrowRight className="size-4" /></Link>
                    </Button>
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
