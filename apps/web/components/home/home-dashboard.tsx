"use client"

/**
 * Authenticated home command surface — literal Nodus structure + configurable widgets.
 * Real metrics only; empty states are honest.
 */

import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, ChevronDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { OperatingFlow } from "@/components/home/operating-flow"
import { NucleoClose } from "@/components/icons/nucleo/semantic"
import { APP_ROUTES } from "@/lib/app-routes"
import { cardVariants, useMotionPrefs } from "@/lib/animations"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { packWidgets } from "@/lib/dashboard/place-widgets"
import type { DashboardRange, DashboardWidget } from "@/lib/dashboard/types"
import { DASHBOARD_PRESETS, KPI_BY_ID } from "@/lib/dashboard/kpi-registry"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import { DashboardWidgetView, resolveKpiValue } from "@/components/home/dashboard-widget-view"
import { KpiPickerDialog } from "@/components/home/kpi-picker-dialog"
import { SystemOutcomes } from "@/components/home/system-outcomes"
import { useDashboardView, useSectionCollapsed, type DashboardView } from "@/lib/dashboard/view-preference"
import type { WelcomeRoleId } from "@/lib/welcome-flow"
import { ROLE_QUICK_ACTIONS } from "@/lib/role-quick-actions"

/** Widgets with their own composition; everything else is a number and joins the measure strip. */
const RICH_WIDGETS = new Set([
  "agents.by_status",
  "runs.breakdown",
  "agents.monitor",
  "gibe.learning_query",
  "gibe.learning_workflow",
  "gibe.revenue_risks",
  "gibe.predictive",
])
const NUMBER_VIZ = new Set(["number", "number_trend", "status", "sparkline"])

// The metrics overview accepts 7d | 30d | 90d only, so shorter ranges are served as 7 days.
const RANGE_LABEL: Record<DashboardRange, string> = {
  "1h": "last 7 days (shortest available)",
  "24h": "last 7 days (shortest available)",
  "7d": "last 7 days",
  "30d": "last 30 days",
  "90d": "last 90 days",
}

type HomeDashboardProps = {
  roleId: WelcomeRoleId
  roleLabel: string
  showGettingStarted: boolean
  showRoleQuickActions?: boolean
  data: HomeDashboardData
  editMode: boolean
  setEditMode: (v: boolean) => void
  globalRange: DashboardRange
  setRange: (r: DashboardRange) => void
  widgets: DashboardWidget[]
  displayedMetricIds: Set<string>
  addWidget: (metricId: string) => void
  removeWidget: (widgetId: string) => void
  reorderWidget: (widgetId: string, toOrder: number) => void
  resizeWidget: (widgetId: string) => void
  resetLayout: () => void
  applyPreset: (presetId: string) => void
  saving?: boolean
}

export function HomeDashboard({
  roleId,
  roleLabel,
  showGettingStarted,
  data,
  editMode,
  setEditMode,
  globalRange,
  setRange,
  widgets,
  displayedMetricIds,
  addWidget,
  removeWidget,
  reorderWidget,
  resizeWidget,
  resetLayout,
  applyPreset,
  saving = false,
}: HomeDashboardProps) {
  const { reduced, container, item } = useMotionPrefs()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [dragId, setDragId] = useState<string | null>(null)
  const [dropOrder, setDropOrder] = useState<number | null>(null)

  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops
  const [view, setView] = useDashboardView()
  // Customizing edits the KPI board, so it always happens in the Reports view.
  const showReports = view === "reports" || editMode
  const changeView = (next: DashboardView) => {
    if (next === "ai" && editMode) setEditMode(false)
    setView(next)
  }
  const startCustomize = () => {
    setView("reports")
    setEditMode(true)
  }

  const { railWidgets, boardWidgets } = useMemo(() => {
    const rail: DashboardWidget[] = []
    const board: DashboardWidget[] = []
    for (const widget of [...widgets].sort((a, b) => a.order - b.order)) {
      if (widget.metricId === "agents.monitor") continue
      if (!RICH_WIDGETS.has(widget.metricId) && NUMBER_VIZ.has(widget.visualization)) rail.push(widget)
      else board.push(widget)
    }
    return { railWidgets: rail, boardWidgets: board }
  }, [widgets])
  const placed = useMemo(
    () => packWidgets(editMode ? widgets : boardWidgets),
    [editMode, widgets, boardWidgets],
  )

  const onDrop = (targetOrder: number) => {
    if (!dragId) return
    reorderWidget(dragId, targetOrder)
    setDragId(null)
    setDropOrder(null)
  }

  return (
    <div className="relative flex min-h-full w-full flex-col overflow-x-hidden bg-[color:var(--g-canvas)]" data-composition="understand">
      {/* Operating command strip — identity, live state, AI command line, range and layout controls */}
      <div
        data-dashboard-command-strip=""
        className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--g-border-default)] px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)]"
      >
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-[20px] font-semibold leading-tight tracking-[-0.02em] text-foreground">Dashboard</h1>
          <DashboardViewToggle view={showReports ? "reports" : "ai"} onChange={changeView} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {showReports ? (
            <Select value={globalRange} onValueChange={(v) => setRange(v as DashboardRange)}>
              <SelectTrigger className="h-8 w-[120px] text-xs" aria-label="Dashboard date range">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1h">Last hour</SelectItem>
                <SelectItem value="24h">24 hours</SelectItem>
                <SelectItem value="7d">7 days</SelectItem>
                <SelectItem value="30d">30 days</SelectItem>
                <SelectItem value="90d">90 days</SelectItem>
              </SelectContent>
            </Select>
          ) : null}
          {editMode ? (
            <>
              <Button type="button" size="sm" variant="outline" className="h-8" onClick={() => setPickerOpen(true)}>
                <span className="mr-1 text-base leading-none">+</span>
                Add KPI
              </Button>
              <Select onValueChange={(presetId) => applyPreset(presetId)}>
                <SelectTrigger className="h-8 w-[140px] text-xs" aria-label="Apply dashboard preset">
                  <SelectValue placeholder="Presets" />
                </SelectTrigger>
                <SelectContent>
                  {DASHBOARD_PRESETS.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id} title={preset.description}>
                      {preset.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="button" size="sm" variant="ghost" className="h-8" onClick={resetLayout}>
                Reset layout
              </Button>
              <Button type="button" size="sm" className="h-8" onClick={() => setEditMode(false)}>
                Done{saving ? "…" : ""}
              </Button>
            </>
          ) : (
            <Button type="button" size="sm" variant="ghost" className="h-8" onClick={startCustomize}>
              Customize
            </Button>
          )}
        </div>
      </div>

      {!showReports ? (
        <div data-dashboard-view="ai" className="flex flex-col">
          <OperatingFlow data={data} quickActions={quickActions} />
          <div className="flex flex-col gap-6 border-t border-[color:var(--g-border-subtle)] px-[var(--np-page-pad-sm)] pb-8 pt-5 sm:px-[var(--np-page-pad)]">
            <SystemOutcomes />
            <OutcomePlaysPreview plays={data.plays} />
            {showGettingStarted ? <GettingStartedNote /> : null}
          </div>
        </div>
      ) : null}

      {showReports && editMode ? (
        <p className={cn(TYPE.meta, "px-[var(--np-page-pad-sm)] pt-4 sm:px-[var(--np-page-pad)]")}>
          Drag widgets to reorder. Use the size button to cycle widths. Your layout is saved for {roleLabel}.
        </p>
      ) : null}

      {/* Reports — the configured KPI board */}
      {showReports ? (
      <motion.section
        data-dashboard-view="reports"
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        aria-labelledby="dashboard-measure"
        className="relative z-10 space-y-4 px-[var(--np-page-pad-sm)] pb-6 pt-4 sm:px-[var(--np-page-pad)] sm:pb-8"
      >
        {!editMode ? (
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="dashboard-measure" className="text-[13px] font-semibold text-foreground">
              Reports
            </h2>
            <span className={TYPE.meta}>Your KPIs · {RANGE_LABEL[globalRange]}</span>
          </div>
        ) : (
          <h2 id="dashboard-measure" className="sr-only">
            Reports
          </h2>
        )}

        {!editMode && widgets.length === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-[var(--np-radius-lg)] border border-dashed border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)] p-5">
            <p className="text-sm font-medium text-foreground">No KPIs on your board yet.</p>
            <p className={TYPE.meta}>Pick the numbers you want to track and they appear here.</p>
            <Button type="button" size="sm" className="h-8" onClick={() => { startCustomize(); setPickerOpen(true) }}>
              Add KPIs
            </Button>
          </div>
        ) : null}

        {!editMode && railWidgets.length > 0 ? (
          <motion.dl
            variants={item}
            className="grid grid-cols-2 divide-x divide-y divide-[color:var(--g-brand-border)] rounded-[var(--np-radius-md)] border border-[color:var(--g-brand-border)] bg-[color:var(--g-brand-surface)] sm:grid-cols-3 lg:auto-cols-fr lg:grid-flow-col lg:grid-cols-none lg:divide-y-0"
          >
            {railWidgets.map((widget) => {
              const resolved = resolveKpiValue(widget.metricId, data)
              const label = widget.title ?? KPI_BY_ID[widget.metricId]?.name ?? widget.metricId
              return (
                <div key={widget.id} className="relative min-w-0 px-3 py-2.5">
                  <dt className="truncate text-[12px] text-muted-foreground">
                    {resolved.href ? (
                      <Link
                        href={resolved.href}
                        className="hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring after:absolute after:inset-0"
                      >
                        {label}
                      </Link>
                    ) : (
                      label
                    )}
                  </dt>
                  <dd
                    className={cn(
                      "mt-0.5 text-lg font-semibold tabular-nums tracking-[-0.01em] text-foreground",
                      resolved.warning && "text-warning",
                      resolved.empty && "text-muted-foreground",
                    )}
                  >
                    {resolved.value}
                  </dd>
                </div>
              )
            })}
          </motion.dl>
        ) : null}

        {!editMode && data.playImpact && (data.playImpact.verifiedResultCount > 0 || data.playImpact.pendingVerificationCount > 0) ? (
          <motion.section variants={item} aria-labelledby="dashboard-play-impact" className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 id="dashboard-play-impact" className="text-sm font-semibold text-foreground">Verified Play impact</h3>
                <p className={cn(TYPE.meta, "mt-1")}>Business results confirmed by a source of record. Workflow completion is not counted as impact.</p>
              </div>
              <Link href={APP_ROUTES.plays} className="text-xs font-medium text-foreground underline-offset-4 hover:underline">View plays</Link>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-[8px] border border-divide bg-[color:var(--g-surface-2)] p-3">
                <p className={TYPE.meta}>Verified results</p>
                <p className="mt-1 text-xl font-semibold tabular-nums">{data.playImpact.verifiedResultCount}</p>
              </div>
              <div className="rounded-lg border border-divide p-3">
                <p className={TYPE.meta}>Pending verification</p>
                <p className="mt-1 text-xl font-semibold tabular-nums">{data.playImpact.pendingVerificationCount}</p>
              </div>
              <div className="rounded-lg border border-divide p-3">
                <p className={TYPE.meta}>Verified measured impact</p>
                {data.playImpact.verifiedMetrics.length ? data.playImpact.verifiedMetrics.slice(0, 2).map((metric) => (
                  <p key={`${metric.metricKey}-${metric.currency ?? ""}`} className="mt-1 text-sm font-semibold tabular-nums">
                    {metric.currency ? `${metric.currency} ` : ""}{metric.value.toLocaleString()} <span className="font-normal text-muted-foreground">{metric.metricKey.replaceAll("_", " ")}</span>
                  </p>
                )) : <p className="mt-1 text-sm text-muted-foreground">No verified measured delta yet</p>}
              </div>
            </div>
          </motion.section>
        ) : null}

        {/* Desktop / tablet grid */}
        <motion.div
          variants={item}
          className="hidden gap-3 md:grid"
          style={{
            gridTemplateColumns: "repeat(12, minmax(0, 1fr))",
            gridAutoRows: "minmax(96px, auto)",
          }}
        >
          {placed.map((widget) => {
            const isDropTarget = dropOrder === widget.order && dragId !== widget.id
            return (
              <div
                key={widget.id}
                className={cn(
                  "relative min-w-0",
                  editMode && "rounded-[10px] ring-offset-2",
                  isDropTarget && "ring-2 ring-[color:var(--g-emerald)]/35",
                )}
                style={{
                  gridColumn: `${widget.x + 1} / span ${widget.w}`,
                  gridRow: `${widget.y + 1} / span ${widget.h}`,
                }}
                draggable={editMode}
                onDragStart={() => setDragId(widget.id)}
                onDragEnd={() => {
                  setDragId(null)
                  setDropOrder(null)
                }}
                onDragOver={(e) => {
                  if (!editMode || !dragId) return
                  e.preventDefault()
                  setDropOrder(widget.order)
                }}
                onDrop={(e) => {
                  e.preventDefault()
                  onDrop(widget.order)
                }}
              >
                {editMode ? (
                  <div className="absolute right-1.5 top-1.5 z-10 flex gap-1">
                    <button
                      type="button"
                      className="rounded-md border border-divide bg-[color:var(--g-surface-1)] px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground shadow-sm hover:text-foreground"
                      onClick={() => resizeWidget(widget.id)}
                      aria-label={`Resize ${KPI_BY_ID[widget.metricId]?.name ?? "widget"}`}
                      title="Cycle size"
                    >
                      {widget.size}
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-divide bg-[color:var(--g-surface-1)] p-1 text-muted-foreground shadow-sm hover:text-foreground"
                      onClick={() => removeWidget(widget.id)}
                      aria-label={`Remove ${KPI_BY_ID[widget.metricId]?.name ?? "widget"}`}
                    >
                      <NucleoClose className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ) : null}
                <div
                  className={cn(
                    "h-full",
                    editMode && "cursor-grab active:cursor-grabbing",
                    dragId === widget.id && "opacity-60",
                  )}
                >
                  <DashboardWidgetView widget={widget} data={data} />
                </div>
              </div>
            )
          })}
        </motion.div>

        {/* Mobile: single column + reorder controls */}
        <motion.div variants={item} className="flex flex-col gap-3 md:hidden">
          {placed.map((widget, index) => (
            <div key={widget.id} className="relative">
              {editMode ? (
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <span className={TYPE.meta}>{KPI_BY_ID[widget.metricId]?.name ?? widget.metricId}</span>
                  <div className="flex gap-1">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs"
                      disabled={index === 0}
                      onClick={() => reorderWidget(widget.id, widget.order - 1)}
                      aria-label="Move up"
                    >
                      ↑
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs"
                      disabled={index >= placed.length - 1}
                      onClick={() => reorderWidget(widget.id, widget.order + 1)}
                      aria-label="Move down"
                    >
                      ↓
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 px-2 text-xs"
                      onClick={() => resizeWidget(widget.id)}
                    >
                      {widget.size}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2"
                      onClick={() => removeWidget(widget.id)}
                      aria-label="Remove widget"
                    >
                      <NucleoClose className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ) : null}
              <DashboardWidgetView widget={widget} data={data} />
            </div>
          ))}
        </motion.div>

        {showGettingStarted ? (
          <motion.div variants={item}>
            <GettingStartedNote />
          </motion.div>
        ) : null}
      </motion.section>
      ) : null}

      <KpiPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        displayedMetricIds={displayedMetricIds}
        onAdd={addWidget}
      />
    </div>
  )
}

const VIEW_OPTIONS: { id: DashboardView; label: string }[] = [
  { id: "ai", label: "AI Native" },
  { id: "reports", label: "Reports" },
]

/** AI Native is the operating briefing; Reports is the KPI board. AI Native is the default. */
function DashboardViewToggle({ view, onChange }: { view: DashboardView; onChange: (view: DashboardView) => void }) {
  return (
    <div
      role="group"
      aria-label="Dashboard view"
      data-dashboard-view-toggle=""
      className="inline-flex items-center rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] p-0.5"
    >
      {VIEW_OPTIONS.map((option) => {
        const active = option.id === view
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.id)}
            className={cn(
              "inline-flex h-7 items-center rounded-full px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-[color:var(--g-brand)] text-white shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

const PLAYS_PREVIEW = 3

function playState(readiness: HomeDashboardData["plays"][number]["readiness"]): { label: string; ready: boolean } {
  if (readiness.act_within_policy_ready) return { label: "Act within policy", ready: true }
  if (readiness.act_with_approval_ready) return { label: "Act with approval", ready: true }
  if (readiness.recommend_ready) return { label: "Ready to recommend", ready: true }
  if (readiness.observe_ready) return { label: "Ready to observe", ready: true }
  if (readiness.dependency_status === "EXTERNAL_CONNECTION_REQUIRED") return { label: "Setup required", ready: false }
  return { label: "Needs attention", ready: false }
}

/** Outcome play readiness as a collapsible preview; the full list lives on the Plays page. */
function OutcomePlaysPreview({ plays }: { plays: HomeDashboardData["plays"] }) {
  const [collapsed, toggle] = useSectionCollapsed("outcome-plays")
  if (plays.length === 0) return null
  const ready = plays.filter(({ readiness }) => playState(readiness).ready).length
  const preview = plays.slice(0, PLAYS_PREVIEW)
  return (
    <section aria-labelledby="dashboard-outcome-plays" data-dashboard-plays="" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="dashboard-outcome-plays-body"
          className="-ml-1 inline-flex min-h-9 items-center gap-1.5 rounded-[6px] px-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronDown
            aria-hidden
            className={cn("size-4 text-muted-foreground transition-transform motion-reduce:transition-none", collapsed && "-rotate-90")}
          />
          <h3 id="dashboard-outcome-plays" className="text-[13px] font-semibold text-foreground">
            Outcome plays
          </h3>
          <span className="ml-1 rounded-full bg-[color:var(--g-brand)]/12 px-2 text-[11.5px] font-medium tabular-nums leading-5 text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]">
            {ready} of {plays.length} ready
          </span>
        </button>
        <span className={TYPE.meta}>Readiness from connected capabilities</span>
      </div>
      {collapsed ? null : (
        <div id="dashboard-outcome-plays-body" className="flex flex-col gap-2">
          <ul className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-subtle)]">
            {preview.map(({ play, readiness, workflowBindingCount }) => {
              const state = playState(readiness)
              return (
                <li
                  key={play.key}
                  className="grid gap-1 py-2.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground">{play.name}</p>
                    <p className={cn(TYPE.meta, "mt-0.5 line-clamp-1")}>{play.objective}</p>
                    <p className={cn(TYPE.meta, "mt-0.5")}>
                      {workflowBindingCount > 0
                        ? `${workflowBindingCount} canonical workflow${workflowBindingCount === 1 ? "" : "s"} bound`
                        : "No canonical workflow bound yet"}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1.5 self-start text-[11px] font-medium tracking-wide sm:self-center",
                      state.ready ? "text-[color:var(--g-brand-active)] dark:text-[color:var(--g-brand)]" : "text-muted-foreground",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn("size-1.5 rounded-full", state.ready ? "bg-[color:var(--g-brand)]" : "bg-warning")}
                    />
                    {state.label}
                  </span>
                </li>
              )
            })}
          </ul>
          <Link
            href={APP_ROUTES.plays}
            className="inline-flex min-h-9 items-center gap-1 self-start text-[12px] font-medium text-[color:var(--g-brand-active)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:text-[color:var(--g-brand)]"
          >
            {plays.length > PLAYS_PREVIEW ? `View all ${plays.length} plays` : "View plays"}
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      )}
    </section>
  )
}

function GettingStartedNote() {
  return (
    <p className={TYPE.meta}>
      Resume setup from{" "}
      <Link href={APP_ROUTES.welcome} className="underline underline-offset-2 hover:text-foreground">
        Getting started
      </Link>
      .
    </p>
  )
}

/** Keep Panel helpers available for optional extended widgets without marketing chrome. */
export function DashboardPanel({
  children,
  reduced,
}: {
  children: ReactNode
  reduced: boolean
}) {
  return (
    <motion.section
      variants={cardVariants}
      whileHover={reduced ? undefined : { y: -1 }}
      className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-3 shadow-[var(--np-shadow)] sm:p-4"
    >
      {children}
    </motion.section>
  )
}
