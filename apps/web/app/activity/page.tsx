"use client"

/**
 * Activity hub — BusinessOutcome list + Failure Alerts tab.
 * Canonical execution surface after IA consolidation (replaces Outcomes / Runs list nav).
 */

import { Suspense, useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"
import { HubFilterBar, HubFilterField } from "@/components/gravitre/hub-filter-bar"
import { FailureAlertsPanel } from "@/components/workflows/failure-alerts-panel"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { businessOutcomesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import { ExternalLink, RefreshCw } from "lucide-react"

type ActivityTab = "all" | "failures"

function asOutcome(raw: Record<string, unknown>): BusinessOutcomeDto {
  return raw as unknown as BusinessOutcomeDto
}

function ActivityPageInner() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const tabParam = searchParams.get("tab")
  const tab: ActivityTab = tabParam === "failures" ? "failures" : "all"

  const [status, setStatus] = useState<string>("all")
  const [lifecycle, setLifecycle] = useState<string>("all")
  const [integration, setIntegration] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const setTab = (next: ActivityTab) => {
    const params = new URLSearchParams(searchParams.toString())
    if (next === "all") params.delete("tab")
    else params.set("tab", next)
    const qs = params.toString()
    router.replace(qs ? `/activity?${qs}` : "/activity")
  }

  const listKey = user
    ? ["business-outcomes", status, lifecycle, integration.trim().toLowerCase()]
    : null

  const { data, error, isLoading, mutate, isValidating } = useSWR(
    listKey,
    () =>
      businessOutcomesApi.list({
        status: status === "all" ? undefined : status,
        lifecycleState: lifecycle === "all" ? undefined : lifecycle,
        integration: integration.trim() || undefined,
        limit: 50,
      }),
    { revalidateOnFocus: true },
  )

  const outcomes = useMemo(
    () => (data?.businessOutcomes ?? []).map((row) => asOutcome(row as Record<string, unknown>)),
    [data],
  )

  const selected =
    outcomes.find((o) => o.id === selectedId) ||
    outcomes.find((o) => o.runId === selectedId) ||
    outcomes[0] ||
    null

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 md:px-6">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">Activity</h1>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Completed work across chat, workflows, and agents — plus predictive failure alerts.
              Same BusinessOutcome records as chat cards.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {tab === "all" ? (
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1.5"
                onClick={() => mutate()}
                disabled={isValidating}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isValidating && "animate-spin")} />
                Refresh
              </Button>
            ) : null}
            <Button asChild variant="outline" size="sm" className="h-8">
              <Link href={APP_ROUTES.audit}>Export audit</Link>
            </Button>
          </div>
        </header>

        <div
          className="flex flex-wrap gap-1 rounded-lg border border-border bg-muted/30 p-1"
          role="tablist"
          aria-label="Activity tabs"
        >
          {(
            [
              { id: "all" as const, label: "All" },
              { id: "failures" as const, label: "Failures" },
            ] as const
          ).map((row) => (
            <button
              key={row.id}
              type="button"
              role="tab"
              aria-selected={tab === row.id}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                tab === row.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setTab(row.id)}
            >
              {row.label}
            </button>
          ))}
        </div>

        {tab === "failures" ? (
          <FailureAlertsPanel />
        ) : (
          <>
            <HubFilterBar>
              <HubFilterField label="Status">
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="h-8">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="running">Running</SelectItem>
                    <SelectItem value="partial_success">Partial success</SelectItem>
                  </SelectContent>
                </Select>
              </HubFilterField>
              <HubFilterField label="Lifecycle">
                <Select value={lifecycle} onValueChange={setLifecycle}>
                  <SelectTrigger className="h-8">
                    <SelectValue placeholder="Lifecycle" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="COMPLETED">COMPLETED</SelectItem>
                    <SelectItem value="partial_success">partial_success</SelectItem>
                    <SelectItem value="failed">failed</SelectItem>
                  </SelectContent>
                </Select>
              </HubFilterField>
              <HubFilterField label="Connector" className="min-w-[160px] flex-1">
                <Input
                  className="h-8"
                  placeholder="e.g. hubspot, apollo, clay"
                  value={integration}
                  onChange={(e) => setIntegration(e.target.value)}
                />
              </HubFilterField>
            </HubFilterBar>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                Could not load activity. Refresh and try again.
              </div>
            ) : null}

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
              <section className="rounded-lg border border-border bg-card">
                <div className="border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Recent ({outcomes.length})
                </div>
                {isLoading ? (
                  <p className="p-4 text-sm text-muted-foreground">Loading activity…</p>
                ) : outcomes.length === 0 ? (
                  <p className="p-4 text-sm text-muted-foreground">
                    No activity yet. Run a workflow or complete work in chat — results land here.
                  </p>
                ) : (
                  <ul className="divide-y divide-border">
                    {outcomes.map((outcome) => {
                      const id = outcome.id || outcome.runId || ""
                      const active =
                        selected?.id === outcome.id || selected?.runId === outcome.runId
                      const meta = outcome.sections?.metadata || {}
                      const pack =
                        typeof meta.pack_id === "string"
                          ? meta.pack_id
                          : typeof meta.packId === "string"
                            ? meta.packId
                            : null
                      return (
                        <li key={id}>
                          <button
                            type="button"
                            className={cn(
                              "flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors hover:bg-muted/40",
                              active && "bg-muted/60",
                            )}
                            onClick={() => setSelectedId(id)}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <span className="line-clamp-2 text-sm font-medium text-foreground">
                                {outcome.title || "Untitled outcome"}
                              </span>
                              <span className="shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">
                                {outcome.lifecycleState || outcome.status || "—"}
                              </span>
                            </div>
                            <p className="line-clamp-2 text-xs text-muted-foreground">
                              {outcome.sections?.summary || "No summary"}
                            </p>
                            <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                              {outcome.sections?.evidence?.integration ? (
                                <span>{String(outcome.sections.evidence.integration)}</span>
                              ) : null}
                              {pack ? <span>pack:{pack}</span> : null}
                              {outcome.source ? <span>{outcome.source}</span> : null}
                              {outcome.runId ? (
                                <Link
                                  href={`/runs/${outcome.runId}`}
                                  className="inline-flex items-center gap-0.5 text-foreground/80 hover:underline"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  Run <ExternalLink className="h-2.5 w-2.5" />
                                </Link>
                              ) : null}
                            </div>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </section>

              <section className="rounded-lg border border-border bg-card p-3 md:p-4">
                <div className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Detail
                </div>
                {selected ? (
                  <BusinessOutcomeView outcome={selected} density="timeline" />
                ) : (
                  <p className="text-sm text-muted-foreground">Select an item to inspect evidence.</p>
                )}
              </section>
            </div>
          </>
        )}
      </div>
    </AppShell>
  )
}

export default function ActivityPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div className="p-6 text-sm text-muted-foreground">Loading activity…</div>
        </AppShell>
      }
    >
      <ActivityPageInner />
    </Suspense>
  )
}
