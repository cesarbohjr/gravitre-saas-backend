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
import { formatStatusLabel } from "@/components/gravitre/status-badge"
import { StatusChip } from "@/components/gravitre/visual"
import { ListSkeleton } from "@/components/gravitre/loading-state"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
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
import { businessOutcomesApi, workObjectsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { cn } from "@/lib/utils"
import { INTERACTION, MOTION, RADIUS, TYPE } from "@/lib/design-system"
import { ExternalLink, RefreshCw, X } from "lucide-react"

type ActivityTab = "all" | "objects" | "failures"

type WorkObjectDto = {
  id: string
  objectType?: string
  department?: string
  title?: string
  objective?: string | null
  owner?: string | null
  status?: string
  priority?: string
  externalEntityType?: string | null
  externalEntityId?: string | null
  systemsInvolved?: string[]
  agentsInvolved?: string[]
  businessOutcomeRefs?: string[]
  outcome?: Record<string, unknown> | null
  roi?: Record<string, unknown> | null
  createdAt?: string | null
  lastActivityAt?: string | null
}

type WorkObjectEventDto = {
  id: string
  eventType?: string
  actionName?: string | null
  actionStatus?: string | null
  systemName?: string | null
  runId?: string | null
  businessOutcomeId?: string | null
  createdAt?: string | null
  evidence?: Record<string, unknown> | null
  outcome?: Record<string, unknown> | null
}

function asOutcome(raw: Record<string, unknown>): BusinessOutcomeDto {
  return raw as unknown as BusinessOutcomeDto
}

function asWorkObject(raw: Record<string, unknown>): WorkObjectDto {
  return raw as unknown as WorkObjectDto
}

function asWorkObjectEvent(raw: Record<string, unknown>): WorkObjectEventDto {
  return raw as unknown as WorkObjectEventDto
}

function ActivityPageInner() {
  const { user } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()
  const tabParam = searchParams.get("tab")
  const tab: ActivityTab =
    tabParam === "failures" ? "failures" : tabParam === "objects" ? "objects" : "all"
  const reduceMotion = useReducedMotion()

  const [status, setStatus] = useState<string>("all")
  const [lifecycle, setLifecycle] = useState<string>("all")
  const [integration, setIntegration] = useState("")
  const [objectType, setObjectType] = useState<string>("all")
  const [objectDepartment, setObjectDepartment] = useState<string>("all")
  const [objectStatus, setObjectStatus] = useState<string>("all")
  const [objectPriority, setObjectPriority] = useState<string>("all")
  const [selectedOutcomeId, setSelectedOutcomeId] = useState<string | null>(null)
  const [selectedWorkObjectId, setSelectedWorkObjectId] = useState<string | null>(null)
  const rowRefs = useRef<Array<HTMLButtonElement | null>>([])

  const setTab = (next: ActivityTab) => {
    const params = new URLSearchParams(searchParams.toString())
    if (next === "all") params.delete("tab")
    else params.set("tab", next)
    const qs = params.toString()
    router.replace(qs ? `/activity?${qs}` : "/activity")
  }

  const listKey = user && tab === "all"
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

  const workObjectListKey =
    user && tab === "objects"
      ? [
          "work-objects",
          objectType,
          objectDepartment,
          objectStatus,
          objectPriority,
        ]
      : null

  const {
    data: workObjectListData,
    error: workObjectListError,
    isLoading: workObjectsLoading,
    mutate: mutateWorkObjects,
    isValidating: workObjectsValidating,
  } = useSWR(
    workObjectListKey,
    () =>
      workObjectsApi.list({
        objectType: objectType === "all" ? undefined : objectType,
        department: objectDepartment === "all" ? undefined : objectDepartment,
        status: objectStatus === "all" ? undefined : objectStatus,
        priority: objectPriority === "all" ? undefined : objectPriority,
        limit: 80,
      }),
    { revalidateOnFocus: true },
  )

  const outcomes = useMemo(
    () => (data?.businessOutcomes ?? []).map((row) => asOutcome(row as Record<string, unknown>)),
    [data],
  )

  const workObjects = useMemo(
    () =>
      (workObjectListData?.workObjects ?? []).map((row) =>
        asWorkObject(row as Record<string, unknown>),
      ),
    [workObjectListData],
  )

  const selectedOutcome =
    outcomes.find((o) => o.id === selectedOutcomeId) ||
    outcomes.find((o) => o.runId === selectedOutcomeId) ||
    outcomes[0] ||
    null

  const selectedWorkObject =
    workObjects.find((o) => o.id === selectedWorkObjectId) || workObjects[0] || null

  const selectedIndex =
    tab === "objects"
      ? selectedWorkObject
        ? workObjects.findIndex((o) => o.id === selectedWorkObject.id)
        : -1
      : selectedOutcome
        ? outcomes.findIndex((o) => o.id === selectedOutcome.id && o.runId === selectedOutcome.runId)
        : -1

  const workObjectDetailKey =
    user && tab === "objects" && selectedWorkObject?.id
      ? ["work-object-detail", selectedWorkObject.id]
      : null
  const { data: workObjectDetailData, isLoading: workObjectDetailLoading } = useSWR(
    workObjectDetailKey,
    () => workObjectsApi.get(String(selectedWorkObject?.id || ""), 250),
    { revalidateOnFocus: true },
  )
  const workObjectEvents = useMemo(
    () =>
      (workObjectDetailData?.events ?? []).map((row) =>
        asWorkObjectEvent(row as Record<string, unknown>),
      ),
    [workObjectDetailData],
  )

  const selected = tab === "objects" ? selectedWorkObject : selectedOutcome

  const hasActiveOutcomeFilters = status !== "all" || lifecycle !== "all" || integration.trim() !== ""
  const activeOutcomeFilterCount =
    (status !== "all" ? 1 : 0) + (lifecycle !== "all" ? 1 : 0) + (integration.trim() ? 1 : 0)
  const hasActiveObjectFilters =
    objectType !== "all" ||
    objectDepartment !== "all" ||
    objectStatus !== "all" ||
    objectPriority !== "all"
  const activeObjectFilterCount =
    (objectType !== "all" ? 1 : 0) +
    (objectDepartment !== "all" ? 1 : 0) +
    (objectStatus !== "all" ? 1 : 0) +
    (objectPriority !== "all" ? 1 : 0)

  const outcomeKey = (outcome: BusinessOutcomeDto) => outcome.id || outcome.runId || ""

  const resetOutcomeFilters = () => {
    setStatus("all")
    setLifecycle("all")
    setIntegration("")
  }

  const resetObjectFilters = () => {
    setObjectType("all")
    setObjectDepartment("all")
    setObjectStatus("all")
    setObjectPriority("all")
  }

  const currentRows = tab === "objects" ? workObjects : outcomes
  // Drives the empty state: "no matches, widen your filters" is a very
  // different message from "nothing has run yet", and conflating them makes a
  // filtered-out list look like a broken product.
  const hasActiveFilters = tab === "objects" ? hasActiveObjectFilters : hasActiveOutcomeFilters
  const activeFilterCount = tab === "objects" ? activeObjectFilterCount : activeOutcomeFilterCount
  const isPanelLoading = tab === "objects" ? workObjectsLoading : isLoading
  const isPanelRefreshing = tab === "objects" ? workObjectsValidating : isValidating
  const panelError = tab === "objects" ? workObjectListError : error

  const resetFilters = () => {
    if (tab === "objects") resetObjectFilters()
    else resetOutcomeFilters()
  }

  const refreshRows = () => {
    if (tab === "objects") mutateWorkObjects()
    else mutate()
  }

  // A listbox that only responds to clicks is a keyboard trap for exactly the
  // audit/compliance users who live in this view. Arrow keys move the selection
  // and follow focus, matching the ARIA listbox pattern.
  const handleListKeyDown = (event: KeyboardEvent<HTMLElement>, index: number) => {
    const lastIndex = currentRows.length - 1
    let next: number | null = null

    if (event.key === "ArrowDown") next = index === lastIndex ? 0 : index + 1
    else if (event.key === "ArrowUp") next = index === 0 ? lastIndex : index - 1
    else if (event.key === "Home") next = 0
    else if (event.key === "End") next = lastIndex

    if (next === null) return
    event.preventDefault()
    const target = currentRows[next]
    if (!target) return
    if (tab === "objects") setSelectedWorkObjectId((target as WorkObjectDto).id)
    else setSelectedOutcomeId(outcomeKey(target as BusinessOutcomeDto))
    rowRefs.current[next]?.focus()
    rowRefs.current[next]?.scrollIntoView({ block: "nearest" })
  }

  // Surface the loaded count on the tab itself so the strip carries information
  // rather than just switching panels. Omitted while loading so it doesn't
  // flash a misleading 0.
  const activityTabs: Array<HubTabItem<ActivityTab>> = [
    { id: "all", label: "All", count: isLoading ? undefined : outcomes.length },
    {
      id: "objects",
      label: "WorkObjects",
      count: workObjectsLoading ? undefined : workObjects.length,
    },
    { id: "failures", label: "Failures" },
  ]

  return (
    <AppShell fillViewport>
      {/* lg+: fill the viewport and delegate scrolling to the panes. Below lg
          there is no vertical budget for split panes, so the page scrolls
          normally and the panes stack. */}
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-4 py-4 md:px-6 lg:h-full lg:min-h-0 lg:overflow-hidden">
        {/* Icon tile + eyebrow + title matches the assignments / marketplace
            header baseline. The supporting lead is deliberately omitted: this
            layout is viewport-locked, and a paragraph here costs the list pane
            a row of vertical budget on short screens. */}
        <header className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div className="flex min-w-0 items-center gap-3">
            <div
              className={cn(
                "hidden h-10 w-10 shrink-0 items-center justify-center border border-primary/20 bg-primary/10 sm:flex",
                RADIUS.tile,
              )}
            >
              <Icon name="activity" size="md" className="text-primary" />
            </div>
            <div className="min-w-0 space-y-0.5">
              <p className={TYPE.eyebrow}>Execution log</p>
              <div className="flex items-center gap-2">
                <h1 className={TYPE.pageTitle}>Activity</h1>
                {/* Reads as "this surface is live" — the list revalidates on
                    focus, so a static header would understate that. */}
                <AnimatePresence>
                  {isPanelRefreshing ? (
                    <motion.span
                      initial={reduceMotion ? false : { opacity: 0, scale: 0.6 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: MOTION.fast }}
                      className="relative flex h-2 w-2"
                      aria-hidden
                    >
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/70" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
                    </motion.span>
                  ) : null}
                </AnimatePresence>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <HubTabs
              tabs={activityTabs}
              active={tab}
              onSelect={setTab}
              ariaLabel="Activity views"
              size="sm"
            />
            {tab === "all" ? (
              <Button
                variant="outline"
                size="sm"
                className={cn("h-8 gap-1.5", RADIUS.control)}
                onClick={refreshRows}
                disabled={isPanelRefreshing}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isPanelRefreshing && "animate-spin")} />
                Refresh
              </Button>
            ) : null}
            {tab === "objects" ? (
              <Button
                variant="outline"
                size="sm"
                className={cn("h-8 gap-1.5", RADIUS.control)}
                onClick={refreshRows}
                disabled={isPanelRefreshing}
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isPanelRefreshing && "animate-spin")} />
                Refresh
              </Button>
            ) : null}
            <Button asChild variant="outline" size="sm" className={cn("h-8", RADIUS.control)}>
              <Link href={APP_ROUTES.audit}>Export audit</Link>
            </Button>
          </div>
        </header>

        {tab === "failures" ? (
          <FailureAlertsPanel />
        ) : (
          <>
            <HubFilterBar compact>
              {tab === "all" ? (
                <>
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
                        <SelectItem value="flagged_for_review">Flagged for review</SelectItem>
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
                        <SelectItem value="created">Created</SelectItem>
                        <SelectItem value="verified">Verified</SelectItem>
                        <SelectItem value="presented">Presented</SelectItem>
                        <SelectItem value="approved">Approved</SelectItem>
                        <SelectItem value="undone">Undone</SelectItem>
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
                </>
              ) : (
                <>
                  <HubFilterField label="Type" compact>
                    <Select value={objectType} onValueChange={setObjectType}>
                      <SelectTrigger className="h-8 w-[170px]">
                        <SelectValue placeholder="Type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All types</SelectItem>
                        <SelectItem value="opportunity">Opportunity</SelectItem>
                        <SelectItem value="campaign">Campaign</SelectItem>
                        <SelectItem value="candidate">Candidate</SelectItem>
                        <SelectItem value="financial_issue">Financial issue</SelectItem>
                        <SelectItem value="ticket">Ticket</SelectItem>
                        <SelectItem value="contract_matter">Contract / matter</SelectItem>
                        <SelectItem value="incident">Incident</SelectItem>
                        <SelectItem value="vulnerability">Vulnerability</SelectItem>
                        <SelectItem value="vendor">Vendor</SelectItem>
                        <SelectItem value="feature">Feature</SelectItem>
                        <SelectItem value="issue_pr">Issue / PR</SelectItem>
                        <SelectItem value="objective">Objective</SelectItem>
                      </SelectContent>
                    </Select>
                  </HubFilterField>
                  <HubFilterField label="Department" compact>
                    <Select value={objectDepartment} onValueChange={setObjectDepartment}>
                      <SelectTrigger className="h-8 w-[160px]">
                        <SelectValue placeholder="Department" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All departments</SelectItem>
                        <SelectItem value="sales">Sales</SelectItem>
                        <SelectItem value="marketing">Marketing</SelectItem>
                        <SelectItem value="hr">HR</SelectItem>
                        <SelectItem value="finance">Finance</SelectItem>
                        <SelectItem value="support">Support</SelectItem>
                        <SelectItem value="legal">Legal</SelectItem>
                        <SelectItem value="security">Security</SelectItem>
                        <SelectItem value="procurement">Procurement</SelectItem>
                        <SelectItem value="engineering">Engineering</SelectItem>
                        <SelectItem value="operations">Operations</SelectItem>
                      </SelectContent>
                    </Select>
                  </HubFilterField>
                  <HubFilterField label="Status" compact>
                    <Select value={objectStatus} onValueChange={setObjectStatus}>
                      <SelectTrigger className="h-8 w-[150px]">
                        <SelectValue placeholder="Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All statuses</SelectItem>
                        <SelectItem value="identified">Identified</SelectItem>
                        <SelectItem value="planned">Planned</SelectItem>
                        <SelectItem value="in_progress">In progress</SelectItem>
                        <SelectItem value="awaiting_approval">Awaiting approval</SelectItem>
                        <SelectItem value="blocked">Blocked</SelectItem>
                        <SelectItem value="completed">Completed</SelectItem>
                        <SelectItem value="failed">Failed</SelectItem>
                      </SelectContent>
                    </Select>
                  </HubFilterField>
                  <HubFilterField label="Priority" compact>
                    <Select value={objectPriority} onValueChange={setObjectPriority}>
                      <SelectTrigger className="h-8 w-[140px]">
                        <SelectValue placeholder="Priority" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All priorities</SelectItem>
                        <SelectItem value="low">Low</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="critical">Critical</SelectItem>
                      </SelectContent>
                    </Select>
                  </HubFilterField>
                </>
              )}
              <AnimatePresence initial={false}>
                {hasActiveFilters ? (
                  <motion.div
                    initial={reduceMotion ? false : { opacity: 0, scale: 0.94 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.94 }}
                    transition={{ duration: MOTION.fast }}
                    className="ml-auto"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn("h-8 gap-1.5 text-xs text-muted-foreground", RADIUS.control)}
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

            {panelError ? (
              <div
                className={cn(
                  "flex items-center gap-2 border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive",
                  RADIUS.card,
                )}
              >
                <Icon name="shieldAlert" size="sm" className="shrink-0" />
                Could not load {tab === "objects" ? "WorkObjects" : "activity"}. Refresh and try again.
              </div>
            ) : null}

            <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row lg:gap-4">
              <section
                className={cn(
                  "flex min-h-0 flex-col overflow-hidden border border-border bg-card shadow-sm lg:w-[380px] lg:shrink-0",
                  RADIUS.panel,
                )}
              >
                {/* Count lives on the tab now — repeating it here read as two
                    different numbers at a glance. */}
                <div
                  className={cn(
                    "shrink-0 border-b border-border bg-gradient-to-b from-muted/40 to-card/95 px-3 py-2 backdrop-blur",
                    TYPE.eyebrow,
                  )}
                >
                  Recent
                </div>
                {/* `relative` anchors the scroll-fade overlay below. */}
                <div className="relative min-h-0 flex-1">
                  {/* Signals more rows below the fold without adding chrome.
                      pointer-events-none so it can never eat a row click. */}
                  <div
                    className="pointer-events-none absolute inset-x-0 bottom-0 z-10 hidden h-8 bg-gradient-to-t from-card to-transparent lg:block"
                    aria-hidden
                  />
                  <div className="min-h-0 h-full lg:overflow-y-auto">
                  {isPanelLoading ? (
                    <ListSkeleton items={5} className="p-3" />
                  ) : currentRows.length === 0 ? (
                    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
                      <div
                        className={cn(
                          "flex h-11 w-11 items-center justify-center border border-border bg-muted/50",
                          RADIUS.tile,
                        )}
                      >
                        <Icon name="activity" size="md" className="text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-foreground">
                          {hasActiveFilters
                            ? `No matching ${tab === "objects" ? "WorkObjects" : "activity"}`
                            : tab === "objects"
                              ? "No WorkObjects yet"
                              : "No activity yet"}
                        </p>
                        <p className="mx-auto mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
                          {hasActiveFilters
                            ? "No results for these filters. Try widening them to see more."
                            : tab === "objects"
                              ? "Complete connector actions in chat or runs and WorkObjects will be attributed here."
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
                      aria-label={tab === "objects" ? "WorkObject list" : "Recent activity"}
                      aria-activedescendant={
                        selected
                          ? tab === "objects"
                            ? `activity-row-${(selected as WorkObjectDto).id}`
                            : `activity-row-${outcomeKey(selected as BusinessOutcomeDto)}`
                          : undefined
                      }
                    >
                      {tab === "objects"
                        ? workObjects.map((workObject, index) => {
                            const id = String(workObject.id || "")
                            const active = selectedWorkObject?.id === id
                            return (
                              <li key={id} role="presentation">
                                <motion.button
                                  type="button"
                                  id={`activity-row-${id}`}
                                  role="option"
                                  aria-selected={active}
                                  tabIndex={index === (selectedIndex === -1 ? 0 : selectedIndex) ? 0 : -1}
                                  ref={(node) => {
                                    rowRefs.current[index] = node
                                  }}
                                  onKeyDown={(event) => handleListKeyDown(event, index)}
                                  initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{
                                    duration: MOTION.base,
                                    delay: reduceMotion ? 0 : Math.min(index, 12) * MOTION.stagger,
                                  }}
                                  className={cn(
                                    "group relative flex w-full flex-col gap-1 py-3 pl-4 pr-3 text-left transition-colors duration-150",
                                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                                    active
                                      ? "bg-gradient-to-r from-primary/[0.07] to-transparent"
                                      : "hover:bg-gradient-to-r hover:from-muted/60 hover:to-transparent",
                                  )}
                                  onClick={() => setSelectedWorkObjectId(id)}
                                >
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
                                      {workObject.title || "Untitled WorkObject"}
                                    </span>
                                    <StatusChip status={String(workObject.status || "identified")} className="shrink-0">
                                      {formatStatusLabel(String(workObject.status || "identified"))}
                                    </StatusChip>
                                  </div>
                                  <p className="line-clamp-2 text-xs text-muted-foreground">
                                    {workObject.objective || "No objective yet"}
                                  </p>
                                  <div className="flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                                    {workObject.objectType ? <span>{workObject.objectType}</span> : null}
                                    {workObject.department ? <span>{workObject.department}</span> : null}
                                    {workObject.priority ? <span>priority:{workObject.priority}</span> : null}
                                    {workObject.systemsInvolved?.[0] ? (
                                      <span>{workObject.systemsInvolved.join(", ")}</span>
                                    ) : null}
                                    {(workObject.businessOutcomeRefs || []).length > 0 ? (
                                      <span>evidence:{(workObject.businessOutcomeRefs || []).length}</span>
                                    ) : null}
                                  </div>
                                </motion.button>
                              </li>
                            )
                          })
                        : outcomes.map((outcome, index) => {
                            const id = outcomeKey(outcome)
                            const active =
                              selectedOutcome?.id === outcome.id && selectedOutcome?.runId === outcome.runId
                            const meta = outcome.sections?.metadata || {}
                            const pack =
                              typeof meta.pack_id === "string"
                                ? meta.pack_id
                                : typeof meta.packId === "string"
                                  ? meta.packId
                                  : null
                            return (
                              <li key={id} role="presentation">
                                <motion.button
                                  type="button"
                                  id={`activity-row-${id}`}
                                  role="option"
                                  aria-selected={active}
                                  tabIndex={index === (selectedIndex === -1 ? 0 : selectedIndex) ? 0 : -1}
                                  ref={(node) => {
                                    rowRefs.current[index] = node
                                  }}
                                  onKeyDown={(event) => handleListKeyDown(event, index)}
                                  initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{
                                    duration: MOTION.base,
                                    delay: reduceMotion ? 0 : Math.min(index, 12) * MOTION.stagger,
                                  }}
                                  className={cn(
                                    "group relative flex w-full flex-col gap-1 py-3 pl-4 pr-3 text-left transition-colors duration-150",
                                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                                    String(outcome.status || "").toLowerCase() === "flagged_for_review" &&
                                      "bg-warning/[0.05]",
                                    active
                                      ? "bg-gradient-to-r from-primary/[0.07] to-transparent"
                                      : "hover:bg-gradient-to-r hover:from-muted/60 hover:to-transparent",
                                  )}
                                  onClick={() => setSelectedOutcomeId(id)}
                                >
                                  {String(outcome.status || "").toLowerCase() === "flagged_for_review" && !active ? (
                                    <span
                                      className="absolute inset-y-0 left-0 w-[3px] bg-warning"
                                      aria-hidden
                                    />
                                  ) : null}
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
                                    {outcome.status || outcome.lifecycleState ? (
                                      <StatusChip
                                        status={String(outcome.status || outcome.lifecycleState)}
                                        className="shrink-0"
                                      >
                                        {formatStatusLabel(String(outcome.status || outcome.lifecycleState))}
                                      </StatusChip>
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
                                    {typeof meta.risk_level === "string" ||
                                    typeof meta.riskLevel === "string" ? (
                                      <span>
                                        risk:{String(meta.risk_level || meta.riskLevel)}
                                      </span>
                                    ) : null}
                                    {typeof meta.estimated_impact === "string" ||
                                    typeof meta.estimatedImpact === "string" ||
                                    outcome.sections?.impact ? (
                                      <span>
                                        impact:
                                        {String(
                                          meta.estimated_impact ||
                                            meta.estimatedImpact ||
                                            outcome.sections?.impact,
                                        )}
                                      </span>
                                    ) : null}
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
                                </motion.button>
                              </li>
                            )
                          })}
                    </ul>
                  )}
                  </div>
                </div>
              </section>

              <section
                className={cn(
                  "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border border-border bg-card shadow-sm",
                  RADIUS.panel,
                )}
              >
                {/* The pane header now names what is selected instead of saying
                    "Detail" over an unlabelled card, and carries the jump to the
                    underlying run — so the list -> outcome -> run trace is one
                    continuous path rather than a hunt inside the body copy. */}
                <div
                  className={cn(
                    "flex shrink-0 items-center justify-between gap-3 border-b border-border bg-gradient-to-b from-muted/40 to-card/95 px-3 py-2 backdrop-blur",
                  )}
                >
                  <span className={cn(TYPE.eyebrow, "truncate")}>
                    {tab === "objects"
                      ? selectedWorkObject?.title || "WorkObject detail"
                      : selectedOutcome?.title || "Detail"}
                  </span>
                  {tab === "objects" ? null : selectedOutcome?.runId ? (
                    <Link
                      href={`/runs/${selectedOutcome.runId}`}
                      className={cn(
                        "inline-flex shrink-0 items-center gap-1 px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground",
                        RADIUS.control,
                        INTERACTION,
                      )}
                    >
                      Open run
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  ) : null}
                </div>
                <div className="min-h-0 flex-1 p-3 lg:overflow-y-auto md:p-4">
                  {isPanelLoading || (tab === "objects" && workObjectDetailLoading) ? (
                    <ListSkeleton items={3} />
                  ) : tab === "objects" && selectedWorkObject ? (
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.div
                        key={selectedWorkObject.id}
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                        transition={{ duration: MOTION.base }}
                        className="space-y-4"
                      >
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusChip status={String(selectedWorkObject.status || "identified")}>
                              {formatStatusLabel(String(selectedWorkObject.status || "identified"))}
                            </StatusChip>
                            {selectedWorkObject.priority ? (
                              <span className="rounded border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                                priority {selectedWorkObject.priority}
                              </span>
                            ) : null}
                            {selectedWorkObject.department ? (
                              <span className="rounded border border-border px-2 py-0.5 text-[11px] text-muted-foreground">
                                {selectedWorkObject.department}
                              </span>
                            ) : null}
                          </div>
                          <p className="text-sm text-foreground">
                            {selectedWorkObject.objective || "No objective recorded yet."}
                          </p>
                        </div>
                        <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                          <p>
                            <strong className="text-foreground">Type:</strong>{" "}
                            {selectedWorkObject.objectType || "objective"}
                          </p>
                          <p>
                            <strong className="text-foreground">Owner:</strong>{" "}
                            {selectedWorkObject.owner || "Unassigned"}
                          </p>
                          <p>
                            <strong className="text-foreground">Systems:</strong>{" "}
                            {(selectedWorkObject.systemsInvolved || []).join(", ") || "None"}
                          </p>
                          <p>
                            <strong className="text-foreground">Agents:</strong>{" "}
                            {(selectedWorkObject.agentsInvolved || []).join(", ") || "None"}
                          </p>
                        </div>
                        <div className="space-y-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Lifecycle timeline
                          </p>
                          {workObjectEvents.length === 0 ? (
                            <p className="text-xs text-muted-foreground">No attributed actions yet.</p>
                          ) : (
                            <ul className="space-y-2">
                              {workObjectEvents.map((event) => (
                                <li key={event.id} className="rounded border border-border bg-muted/30 p-2">
                                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                                    <span className="font-medium text-foreground">
                                      {event.actionName || event.eventType || "action"}
                                    </span>
                                    <StatusChip status={String(event.actionStatus || "completed")}>
                                      {formatStatusLabel(String(event.actionStatus || "completed"))}
                                    </StatusChip>
                                  </div>
                                  <p className="mt-1 text-xs text-muted-foreground">
                                    {event.systemName ? `${event.systemName} · ` : ""}
                                    {event.createdAt || "timestamp unavailable"}
                                  </p>
                                  {event.runId ? (
                                    <Link href={`/runs/${event.runId}`} className="mt-1 inline-flex items-center gap-1 text-xs hover:underline">
                                      Open run
                                      <ExternalLink className="h-3 w-3" />
                                    </Link>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </motion.div>
                    </AnimatePresence>
                  ) : selectedOutcome ? (
                    // Keyed cross-fade so switching rows reads as a transition
                    // rather than the pane contents teleporting.
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.div
                        key={outcomeKey(selectedOutcome)}
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -6 }}
                        transition={{ duration: MOTION.base }}
                      >
                        <BusinessOutcomeView outcome={selectedOutcome} density="timeline" />
                      </motion.div>
                    </AnimatePresence>
                  ) : (
                    <div className="flex flex-col items-center gap-3 py-10 text-center">
                      <div
                        className={cn(
                          "flex h-11 w-11 items-center justify-center border border-border bg-muted/50",
                          RADIUS.tile,
                        )}
                      >
                        <Icon name="search" size="md" className="text-muted-foreground" />
                      </div>
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
        <AppShell fillViewport>
          <CenteredLoader fill="parent" label="Loading activity" />
        </AppShell>
      }
    >
      <ActivityPageInner />
    </Suspense>
  )
}
