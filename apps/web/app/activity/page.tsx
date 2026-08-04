"use client"

/**
 * Activity hub — BusinessOutcome list + Failure Alerts tab.
 * Canonical execution surface after IA consolidation (replaces Outcomes / Runs list nav).
 *
 * Layout: a viewport-locked two-pane inspector (email-client / Sentry shaped).
 * The page itself never scrolls at `lg`+ — the list and the detail pane each own
 * their own scroll container. Previously everything (header, tabs, filters, 50
 * rows and the full detail card) stacked into one very tall document.
 */

import { Suspense, useMemo, useRef, useState, type KeyboardEvent } from "react"
import useSWR from "swr"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  BusinessOutcomeView,
  type BusinessOutcomeDto,
} from "@/components/gravitre/business-outcome/business-outcome-view"
import { HubFilterBar, HubFilterField } from "@/components/gravitre/hub-filter-bar"
import { HubTabs, type HubTabItem } from "@/components/gravitre/hub-tabs"
import { AutoStatusBadge } from "@/components/gravitre/status-badge"
import { ListSkeleton } from "@/components/gravitre/loading-state"
import { CenteredLoader } from "@/components/gravitre/gravitree-loader"
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
import { Icon } from "@/lib/icons"
import { businessOutcomesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import { ExternalLink, RefreshCw, X } from "lucide-react"

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
  const reduceMotion = useReducedMotion()

  const [status, setStatus] = useState<string>("all")
  const [lifecycle, setLifecycle] = useState<string>("all")
  const [integration, setIntegration] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([])

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

  const selectedIndex = selected
    ? outcomes.findIndex((o) => o.id === selected.id && o.runId === selected.runId)
    : -1

  const outcomeKey = (outcome: BusinessOutcomeDto) => outcome.id || outcome.runId || ""

  // Drives the empty state: "no matches, widen your filters" is a very
  // different message from "nothing has run yet", and conflating them makes a
  // filtered-out list look like a broken product.
  const hasActiveFilters = status !== "all" || lifecycle !== "all" || integration.trim() !== ""
  const activeFilterCount =
    (status !== "all" ? 1 : 0) + (lifecycle !== "all" ? 1 : 0) + (integration.trim() ? 1 : 0)

  const resetFilters = () => {
    setStatus("all")
    setLifecycle("all")
    setIntegration("")
  }

  // A listbox that only responds to clicks is a keyboard trap for exactly the
  // audit/compliance users who live in this view. Arrow keys move the selection
  // and follow focus, matching the ARIA listbox pattern.
  const handleListKeyDown = (event: KeyboardEvent<HTMLElement>, index: number) => {
    const lastIndex = outcomes.length - 1
    let next: number | null = null

    if (event.key === "ArrowDown") next = index === lastIndex ? 0 : index + 1
    else if (event.key === "ArrowUp") next = index === 0 ? lastIndex : index - 1
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = lastIndex

    if (next === null) return
    event.preventDefault()
    const target = outcomes[next]
    if (!target) return
    setSelectedId(outcomeKey(target))
    rowRefs.current[next]?.focus()
    rowRefs.current[next]?.scrollIntoView({ block: "nearest" })
  }

  // Surface the loaded count on the tab itself so the strip carries information
  // rather than just switching panels. Omitted while loading so it doesn't
  // flash a misleading 0.
  const activityTabs: Array<HubTabItem<ActivityTab>> = [
    { id: "all", label: "All", count: isLoading ? undefined : outcomes.length },
    { id: "failures", label: "Failures" },
  ]

  return (
    <AppShell fillViewport>
      {/* lg+: fill the viewport and delegate scrolling to the panes. Below lg
          there is no vertical budget for split panes, so the page scrolls
          normally and the panes stack. */}
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-4 py-4 md:px-6 lg:h-full lg:min-h-0 lg:overflow-hidden">
        <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
            <h1 className="text-lg font-semibold tracking-tight text-foreground">Activity</h1>
            <HubTabs
              tabs={activityTabs}
              active={tab}
              onSelect={setTab}
              ariaLabel="Activity views"
              size="sm"
            />
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

        {tab === "failures" ? (
          <FailureAlertsPanel />
        ) : (
          <>
            <HubFilterBar compact>
              <HubFilterField label="Status" compact>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger className="h-8 w-[140px]">
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
              <HubFilterField label="Lifecycle" compact>
                <Select value={lifecycle} onValueChange={setLifecycle}>
                  <SelectTrigger className="h-8 w-[150px]">
                    <SelectValue placeholder="Lifecycle" />
                  </SelectTrigger>
                  <SelectContent>
                    {/* Values stay exactly as the API expects them; only the
                        labels are humanized so raw enums don't leak into the UI. */}
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="COMPLETED">Completed</SelectItem>
                    <SelectItem value="partial_success">Partial success</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                  </SelectContent>
                </Select>
              </HubFilterField>
              <HubFilterField label="Connector" compact className="min-w-[180px] flex-1">
                <Input
                  className="h-8"
                  placeholder="e.g. hubspot, apollo, clay"
                  value={integration}
                  onChange={(e) => setIntegration(e.target.value)}
                />
              </HubFilterField>
              <AnimatePresence initial={false}>
                {hasActiveFilters ? (
                  <motion.div
                    initial={reduceMotion ? false : { opacity: 0, scale: 0.94 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.94 }}
                    transition={{ duration: 0.15 }}
                    className="ml-auto"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 gap-1.5 text-xs text-muted-foreground"
                      onClick={resetFilters}
                    >
                      {activeFilterCount} filter{activeFilterCount === 1 ? "" : "s"}
                      <X className="h-3 w-3" />
                      <span className="sr-only">Clear filters</span>
                    </Button>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </HubFilterBar>

            {error ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                Could not load activity. Refresh and try again.
              </div>
            ) : null}

            <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row lg:gap-4">
              <section className="flex min-h-0 flex-col overflow-hidden rounded-lg border border-border bg-card lg:w-[380px] lg:shrink-0">
                {/* Count lives on the tab now — repeating it here read as two
                    different numbers at a glance. */}
                <div className="shrink-0 border-b border-border bg-card/95 px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground backdrop-blur">
                  Recent
                </div>
                <div className="min-h-0 flex-1 lg:overflow-y-auto">
                  {isLoading ? (
                    <ListSkeleton items={5} className="p-3" />
                  ) : outcomes.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
                      <Icon name="activity" size="lg" className="text-muted-foreground/50" />
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {hasActiveFilters ? "No matching activity" : "No activity yet"}
                        </p>
                        <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
                          {hasActiveFilters
                            ? "No results for these filters. Try widening them to see more."
                            : "Run a workflow or complete work in chat — results land here automatically."}
                        </p>
                      </div>
                      {hasActiveFilters ? (
                        <Button variant="outline" size="sm" className="h-8" onClick={resetFilters}>
                          Clear filters
                        </Button>
                      ) : (
                        <Button asChild size="sm" className="h-8">
                          <Link href={APP_ROUTES.gravitreAi}>Start in chat</Link>
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ul
                      className="divide-y divide-border"
                      role="listbox"
                      aria-label="Recent activity"
                      aria-activedescendant={
                        selected ? `activity-row-${outcomeKey(selected)}` : undefined
                      }
                    >
                      {outcomes.map((outcome, index) => {
                        const id = outcomeKey(outcome)
                        const active =
                          selected?.id === outcome.id && selected?.runId === outcome.runId
                        const meta = outcome.sections?.metadata || {}
                        const pack =
                          typeof meta.pack_id === "string"
                            ? meta.pack_id
                            : typeof meta.packId === "string"
                              ? meta.packId
                              : null
                        return (
                          <li key={id} role="presentation">
                            <button
                              type="button"
                              id={`activity-row-${id}`}
                              role="option"
                              aria-selected={active}
                              tabIndex={index === (selectedIndex === -1 ? 0 : selectedIndex) ? 0 : -1}
                              ref={(node) => {
                                rowRefs.current[index] = node
                              }}
                              onKeyDown={(event) => handleListKeyDown(event, index)}
                              className={cn(
                                "relative flex w-full flex-col gap-1 py-3 pl-4 pr-3 text-left transition-colors",
                                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                                active ? "bg-muted/60" : "hover:bg-muted/40",
                              )}
                              onClick={() => setSelectedId(id)}
                            >
                              {/* One accent bar shared across rows, so selection
                                  slides rather than blinking between positions. */}
                              {active ? (
                                <motion.span
                                  layoutId="activity-row-accent"
                                  className="absolute inset-y-0 left-0 w-[3px] bg-primary"
                                  transition={
                                    reduceMotion
                                      ? { duration: 0 }
                                      : { type: "spring", stiffness: 420, damping: 34 }
                                  }
                                  aria-hidden
                                />
                              ) : null}
                              <div className="flex items-start justify-between gap-2">
                                <span className="line-clamp-2 text-sm font-medium text-foreground">
                                  {outcome.title || "Untitled outcome"}
                                </span>
                                {outcome.lifecycleState || outcome.status ? (
                                  <AutoStatusBadge
                                    status={String(outcome.lifecycleState || outcome.status)}
                                    className="shrink-0"
                                  />
                                ) : null}
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
                </div>
              </section>

              <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card">
                <div className="shrink-0 border-b border-border px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Detail
                </div>
                <div className="min-h-0 flex-1 p-3 lg:overflow-y-auto md:p-4">
                  {isLoading ? (
                    <ListSkeleton items={3} />
                  ) : selected ? (
                    // Keyed cross-fade so switching rows reads as a transition
                    // rather than the pane contents teleporting.
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.div
                        key={outcomeKey(selected)}
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                        transition={{ duration: 0.18 }}
                      >
                        <BusinessOutcomeView outcome={selected} density="timeline" />
                      </motion.div>
                    </AnimatePresence>
                  ) : (
                    <div className="flex flex-col items-center gap-2 py-10 text-center">
                      <Icon name="search" size="lg" className="text-muted-foreground/50" />
                      <p className="text-sm font-medium text-foreground">Nothing selected</p>
                      <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
                        Pick an item from the list to inspect its evidence and timeline.
                      </p>
                    </div>
                  )}
                </div>
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
          <CenteredLoader fill="parent" label="Loading activity" />
        </AppShell>
      }
    >
      <ActivityPageInner />
    </Suspense>
  )
}
