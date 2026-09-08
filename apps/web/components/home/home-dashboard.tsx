"use client"

/**
 * Authenticated home command surface — literal Nodus structure + configurable widgets.
 * Real metrics only; empty states are honest.
 */

import type { ReactNode } from "react"
import { useMemo, useState } from "react"
import Link from "next/link"
import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product/page-header"
import { NucleoActivity, NucleoClose } from "@/components/icons/nucleo/semantic"
import { APP_ROUTES } from "@/lib/app-routes"
import { cardVariants, useMotionPrefs } from "@/lib/animations"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { packWidgets } from "@/lib/dashboard/place-widgets"
import type { DashboardRange, DashboardWidget } from "@/lib/dashboard/types"
import { KPI_BY_ID } from "@/lib/dashboard/kpi-registry"
import type { HomeDashboardData } from "@/hooks/use-home-dashboard-data"
import { DashboardWidgetView } from "@/components/home/dashboard-widget-view"
import { KpiPickerDialog } from "@/components/home/kpi-picker-dialog"
import type { WelcomeRoleId } from "@/lib/welcome-flow"
import { ROLE_QUICK_ACTIONS } from "@/lib/role-quick-actions"

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
  saving?: boolean
}

export function HomeDashboard({
  roleId,
  roleLabel,
  showGettingStarted,
  showRoleQuickActions = false,
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
  saving = false,
}: HomeDashboardProps) {
  const { reduced, container, item } = useMotionPrefs()
  const [pickerOpen, setPickerOpen] = useState(false)
  const [dragId, setDragId] = useState<string | null>(null)
  const [dropOrder, setDropOrder] = useState<number | null>(null)

  const quickActions = ROLE_QUICK_ACTIONS[roleId] ?? ROLE_QUICK_ACTIONS.ops
  const showQuickActions =
    (showRoleQuickActions || showGettingStarted) && quickActions.length > 0 && !editMode

  const placed = useMemo(() => packWidgets(widgets), [widgets])

  const onDrop = (targetOrder: number) => {
    if (!dragId) return
    reorderWidget(dragId, targetOrder)
    setDragId(null)
    setDropOrder(null)
  }

  return (
    <div className="relative w-full overflow-x-hidden bg-[color:var(--g-canvas)]">
      <GravitrePageHeader
        title="Dashboard"
        icon={<NucleoActivity className="h-5 w-5" />}
        actions={
          <div className="flex flex-wrap items-center gap-2">
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
            {editMode ? (
              <>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() => setPickerOpen(true)}
                >
                  <span className="mr-1 text-base leading-none">+</span>
                  Add KPI
                </Button>
                <Button type="button" size="sm" variant="ghost" className="h-8" onClick={resetLayout}>
                  Reset layout
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="h-8"
                  onClick={() => setEditMode(false)}
                >
                  Done{saving ? "…" : ""}
                </Button>
              </>
            ) : (
              <>
                {data.pendingApprovals > 0 ? (
                  <Button asChild size="sm" variant="outline" className="h-8">
                    <Link href={APP_ROUTES.approvals}>
                      {data.pendingApprovals} approval{data.pendingApprovals === 1 ? "" : "s"}
                    </Link>
                  </Button>
                ) : null}
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-8"
                  onClick={() => setEditMode(true)}
                >
                  Customize
                </Button>
                {showQuickActions
                  ? quickActions.slice(0, 2).map((action) => (
                      <Button
                        key={action.href}
                        asChild
                        size="sm"
                        variant="ghost"
                        className="h-8 text-muted-foreground"
                      >
                        <Link href={action.href}>{action.label}</Link>
                      </Button>
                    ))
                  : null}
              </>
            )}
          </div>
        }
      />

      <motion.div
        variants={reduced ? undefined : container}
        initial="initial"
        animate="animate"
        className="relative z-10 mx-auto max-w-[1400px] space-y-3 px-[var(--np-page-pad-sm)] py-3 sm:px-[var(--np-page-pad)] sm:pb-6"
      >
        {editMode ? (
          <p className={cn(TYPE.meta)}>
            Drag widgets to reorder — the grid reflows automatically. Resize cycles size presets.
            Layout saves for {roleLabel}.
          </p>
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
                  editMode && "rounded-[var(--np-radius-lg)] ring-offset-2",
                  isDropTarget && "ring-2 ring-[color:var(--brand)]/40",
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
          <motion.p variants={item} className={TYPE.meta}>
            Resume setup from{" "}
            <Link href={APP_ROUTES.welcome} className="underline underline-offset-2 hover:text-foreground">
              Getting Started
            </Link>
            .
          </motion.p>
        ) : null}
      </motion.div>

      <KpiPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        displayedMetricIds={displayedMetricIds}
        onAdd={addWidget}
      />
    </div>
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
