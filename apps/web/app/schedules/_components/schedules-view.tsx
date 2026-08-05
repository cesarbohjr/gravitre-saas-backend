"use client"

import { useEffect, useMemo, useState } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  CalendarDays,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  GanttChartSquare,
  List as ListIcon,
} from "lucide-react"
import {
  KIND_STYLES,
  buildOccurrences,
  type ScheduleKind,
  type ScheduledItem,
  type ScheduleOccurrence,
} from "@/lib/schedules"
import {
  KindDot,
  ScheduleLegend,
  addDays,
  endOfMonth,
  startOfCalendarGrid,
  startOfMonth,
  startOfWeek,
} from "./shared"
import { CalendarView } from "./calendar-view"
import { WeekView } from "./week-view"
import { DayView } from "./day-view"
import { MobileAgenda } from "./mobile-agenda"
import { GanttView } from "./gantt-view"
import { ListView } from "./list-view"
import { ScheduleItemDialog } from "./schedule-item-dialog"
import { moveScheduledItem } from "@/lib/schedules/actions"
import { scheduleMoveDescription } from "@/lib/schedules/actions"

type ViewMode = "calendar" | "gantt" | "list"
type CalendarScope = "month" | "week" | "day"

const VIEWS: { id: ViewMode; label: string; icon: typeof CalendarDays }[] = [
  { id: "calendar", label: "Calendar", icon: CalendarDays },
  { id: "gantt", label: "Gantt", icon: GanttChartSquare },
  { id: "list", label: "List", icon: ListIcon },
]

const CALENDAR_SCOPES: { id: CalendarScope; label: string }[] = [
  { id: "month", label: "Month" },
  { id: "week", label: "Week" },
  { id: "day", label: "Day" },
]

const ALL_KINDS: ScheduleKind[] = ["workflow", "task", "job"]

export interface SchedulesViewProps {
  items: ScheduledItem[]
  /** Show loading skeletons (first load, before any items arrive). */
  loading?: boolean
  /** Notified with the visible window so the parent can drive the data fetch. */
  onRangeChange?: (from: Date, to: Date) => void
  /** Notified when the active kind filter changes. */
  onActiveKindsChange?: (kinds: ScheduleKind[]) => void
  /** Optional workflow filter (global view only). */
  workflowOptions?: { id: string; name: string }[]
  workflowId?: string
  onWorkflowChange?: (workflowId: string | undefined) => void
  onRefresh?: () => void
}

export function SchedulesView({
  items,
  loading = false,
  onRangeChange,
  onActiveKindsChange,
  workflowOptions = [],
  workflowId,
  onWorkflowChange,
  onRefresh,
}: SchedulesViewProps) {
  const [view, setView] = useState<ViewMode>("calendar")
  const [calendarScope, setCalendarScope] = useState<CalendarScope>("month")
  const [focusDate, setFocusDate] = useState(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  })
  const [activeKinds, setActiveKinds] = useState<Set<ScheduleKind>>(new Set(ALL_KINDS))
  const [selectedOccurrence, setSelectedOccurrence] = useState<ScheduleOccurrence | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [pendingMove, setPendingMove] = useState<{
    occurrence: ScheduleOccurrence
    targetDate: Date
  } | null>(null)
  const [isMoving, setIsMoving] = useState(false)
  const reduceMotion = useReducedMotion()

  const month = useMemo(() => startOfMonth(focusDate), [focusDate])

  const filteredItems = useMemo(
    () => items.filter((item) => activeKinds.has(item.kind)),
    [items, activeKinds],
  )

  // Visible fetch window — month grid (6 weeks) covers week/day; gantt uses month.
  const rangeStart = useMemo(() => startOfCalendarGrid(month), [month])
  const rangeEnd = useMemo(() => {
    const end = new Date(rangeStart)
    end.setDate(end.getDate() + 41)
    end.setHours(23, 59, 59, 999)
    return end
  }, [rangeStart])

  const occurrences = useMemo(
    () => buildOccurrences(filteredItems, rangeStart, rangeEnd),
    [filteredItems, rangeStart, rangeEnd],
  )

  // Lift the visible window and active kinds up so the parent page can pass
  // them to the unified /api/schedules endpoint (server-side filtering +
  // cron projection). Callbacks should be memoized by the parent.
  useEffect(() => {
    onRangeChange?.(rangeStart, rangeEnd)
  }, [rangeStart, rangeEnd, onRangeChange])

  useEffect(() => {
    onActiveKindsChange?.(ALL_KINDS.filter((k) => activeKinds.has(k)))
  }, [activeKinds, onActiveKindsChange])

  const monthStart = startOfMonth(month)
  const monthEnd = endOfMonth(month)

  const shiftFocus = (direction: -1 | 1) => {
    setFocusDate((current) => {
      if (view === "calendar" && calendarScope === "week") {
        return addDays(current, direction * 7)
      }
      if (view === "calendar" && calendarScope === "day") {
        return addDays(current, direction)
      }
      return new Date(current.getFullYear(), current.getMonth() + direction, 1)
    })
  }

  const goToday = () => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    setFocusDate(d)
  }

  const periodLabel = useMemo(() => {
    if (view === "calendar" && calendarScope === "week") {
      const start = startOfWeek(focusDate)
      const end = addDays(start, 6)
      const sameMonth = start.getMonth() === end.getMonth()
      const startLabel = start.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })
      const endLabel = end.toLocaleDateString(undefined, {
        month: sameMonth ? undefined : "short",
        day: "numeric",
        year: "numeric",
      })
      return `${startLabel} – ${endLabel}`
    }
    if (view === "calendar" && calendarScope === "day") {
      return focusDate.toLocaleDateString(undefined, {
        weekday: "short",
        month: "long",
        day: "numeric",
        year: "numeric",
      })
    }
    return focusDate.toLocaleString(undefined, { month: "long", year: "numeric" })
  }, [view, calendarScope, focusDate])

  const handleSelect = (target: ScheduledItem | ScheduleOccurrence) => {
    const occurrence = toOccurrence(target)
    setSelectedOccurrence(occurrence)
  }

  const handleOpen = (target: ScheduledItem | ScheduleOccurrence) => {
    const occurrence = toOccurrence(target)
    setSelectedOccurrence(occurrence)
    setDialogOpen(true)
  }

  const confirmMove = async () => {
    if (!pendingMove) return
    setIsMoving(true)
    try {
      await moveScheduledItem(pendingMove.occurrence.item, pendingMove.targetDate)
      toast.success("Schedule updated")
      setPendingMove(null)
      onRefresh?.()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not move schedule")
    } finally {
      setIsMoving(false)
    }
  }

  const toggleKind = (kind: ScheduleKind) => {
    setActiveKinds((prev) => {
      const next = new Set(prev)
      if (next.has(kind)) next.delete(kind)
      else next.add(kind)
      // Never allow an empty selection — reset to all.
      if (next.size === 0) return new Set(ALL_KINDS)
      return next
    })
  }

  const counts = useMemo(() => {
    const c: Record<ScheduleKind, number> = { workflow: 0, task: 0, job: 0 }
    for (const item of filteredItems) c[item.kind] += 1
    return c
  }, [filteredItems])

  return (
    <div className="space-y-4">
      {/* Toolbar — one panel so the month, the view switcher and the type
          filters read as a single control surface instead of three cards. */}
      <div className="space-y-3 rounded-2xl border border-border bg-card p-3 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          {/* Period nav (calendar + gantt) */}
          {view !== "list" ? (
            <div className="flex min-w-0 items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-full sm:h-9 sm:w-9"
                onClick={() => shiftFocus(-1)}
                aria-label={
                  view === "calendar" && calendarScope === "day"
                    ? "Previous day"
                    : view === "calendar" && calendarScope === "week"
                      ? "Previous week"
                      : "Previous month"
                }
              >
                <ChevronLeft className="h-5 w-5 sm:h-4 sm:w-4" />
              </Button>
              <h2 className="min-w-0 flex-1 truncate text-lg font-semibold tracking-tight text-foreground lg:min-w-[11rem] lg:text-xl">
                {periodLabel}
              </h2>
              <Button
                variant="outline"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-full sm:h-9 sm:w-9"
                onClick={() => shiftFocus(1)}
                aria-label={
                  view === "calendar" && calendarScope === "day"
                    ? "Next day"
                    : view === "calendar" && calendarScope === "week"
                      ? "Next week"
                      : "Next month"
                }
              >
                <ChevronRight className="h-5 w-5 sm:h-4 sm:w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-10 shrink-0 rounded-full px-4 sm:h-9"
                onClick={goToday}
              >
                Today
              </Button>
            </div>
          ) : (
            <h2 className="text-lg font-semibold tracking-tight text-foreground lg:text-xl">
              All schedules
            </h2>
          )}

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
            {/* Month / Week / Day — only when Calendar is active */}
            {view === "calendar" ? (
              <div className="inline-flex gap-1 rounded-full border border-border bg-muted/50 p-1">
                {CALENDAR_SCOPES.map((scope) => {
                  const active = calendarScope === scope.id
                  return (
                    <button
                      key={scope.id}
                      type="button"
                      onClick={() => setCalendarScope(scope.id)}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-xs font-medium transition-colors sm:text-sm",
                        active
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground",
                      )}
                      aria-pressed={active}
                    >
                      {scope.id === "week" ? <CalendarRange className="h-3.5 w-3.5" /> : null}
                      {scope.label}
                    </button>
                  )
                })}
              </div>
            ) : null}

            {/* View switcher — full width on phones so the targets stay tappable */}
            <div className="grid grid-cols-3 gap-1 rounded-full border border-border bg-muted/50 p-1 lg:inline-flex lg:w-auto">
              {VIEWS.map((v) => {
                const Icon = v.icon
                const active = view === v.id
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setView(v.id)}
                    className={cn(
                      "inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-2 text-sm font-medium transition-colors sm:py-1.5",
                      active
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                    aria-pressed={active}
                  >
                    <Icon className="h-4 w-4" />
                    {v.label}
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Type filters + workflow scope + legend (scrollable so Training job never clips) */}
        <div className="flex flex-col gap-3 border-t border-border/70 pt-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {ALL_KINDS.map((kind) => {
              const active = activeKinds.has(kind)
              const kindColor = KIND_STYLES[kind].color
              return (
                <button
                  key={kind}
                  type="button"
                  onClick={() => toggleKind(kind)}
                  className={cn(
                    "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                    !active && "border-border text-muted-foreground hover:text-foreground",
                  )}
                  style={
                    active
                      ? {
                          backgroundColor: `color-mix(in oklab, ${kindColor} 16%, transparent)`,
                          borderColor: `color-mix(in oklab, ${kindColor} 45%, transparent)`,
                          color: kindColor,
                        }
                      : undefined
                  }
                  aria-pressed={active}
                >
                  <KindDot kind={kind} className={cn(!active && "opacity-40")} />
                  {KIND_STYLES[kind].label}
                  <span className="rounded-full bg-foreground/10 px-1.5 text-[10px] font-semibold tabular-nums">
                    {counts[kind]}
                  </span>
                </button>
              )
            })}
          </div>
          <div className="flex min-w-0 items-center gap-3 overflow-x-auto pb-0.5 [-ms-overflow-style:none] [scrollbar-width:thin] xl:max-w-[50%] xl:justify-end">
            {workflowOptions && workflowOptions.length > 0 && (
              <Select
                value={workflowId ?? "all"}
                onValueChange={(v) => onWorkflowChange?.(v === "all" ? undefined : v)}
              >
                <SelectTrigger
                  className="h-10 w-[180px] shrink-0 rounded-full text-xs sm:h-9 sm:w-[200px]"
                  aria-label="Filter by workflow"
                >
                  <SelectValue placeholder="All workflows" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All workflows</SelectItem>
                  {workflowOptions.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
            <ScheduleLegend />
          </div>
        </div>
      </div>

      {/* Active view */}
      {loading && items.length === 0 ? (
        <ViewSkeleton view={view} />
      ) : (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={`${view}:${calendarScope}`}
            initial={reduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
          >
            {view === "calendar" && (
              <>
                {/* Phones: week strip + agenda (month/week) or day timeline. */}
                <div className="md:hidden">
                  {calendarScope === "day" ? (
                    <DayView
                      focusDate={focusDate}
                      occurrences={occurrences}
                      selectedId={selectedOccurrence?.item.id}
                      onSelect={handleSelect}
                      onOpen={handleOpen}
                    />
                  ) : (
                    <MobileAgenda
                      month={month}
                      occurrences={occurrences}
                      onOpen={handleOpen}
                      onMonthChange={(nextMonth) => {
                        setFocusDate(nextMonth)
                      }}
                    />
                  )}
                </div>
                <div className="hidden md:block">
                  {calendarScope === "month" ? (
                    <CalendarView
                      month={month}
                      occurrences={occurrences}
                      selectedId={selectedOccurrence?.item.id}
                      onSelect={handleSelect}
                      onOpen={handleOpen}
                      onMoveRequest={(occurrence, targetDate) =>
                        setPendingMove({ occurrence, targetDate })
                      }
                    />
                  ) : null}
                  {calendarScope === "week" ? (
                    <WeekView
                      focusDate={focusDate}
                      occurrences={occurrences}
                      selectedId={selectedOccurrence?.item.id}
                      onSelect={handleSelect}
                      onOpen={handleOpen}
                    />
                  ) : null}
                  {calendarScope === "day" ? (
                    <DayView
                      focusDate={focusDate}
                      occurrences={occurrences}
                      selectedId={selectedOccurrence?.item.id}
                      onSelect={handleSelect}
                      onOpen={handleOpen}
                    />
                  ) : null}
                </div>
              </>
            )}
            {view === "gantt" && (
              <>
                <GanttView
                  rangeStart={monthStart}
                  rangeEnd={monthEnd}
                  occurrences={occurrences.filter(
                    (o) => o.date >= monthStart && o.date <= monthEnd,
                  )}
                  selectedId={selectedOccurrence?.item.id}
                  onSelect={handleSelect}
                  onOpen={handleOpen}
                />
                {occurrences.filter((o) => o.date >= monthStart && o.date <= monthEnd).length ===
                  0 && <EmptyRange label="No scheduled items this month." />}
              </>
            )}
            {view === "list" && (
              <ListView
                items={filteredItems}
                selectedId={selectedOccurrence?.item.id}
                onSelect={handleSelect}
                onOpen={handleOpen}
              />
            )}
          </motion.div>
        </AnimatePresence>
      )}

      <p className="px-1 text-xs text-muted-foreground">
        Tip: tap an item to reschedule or edit
        <span className="hidden md:inline">, or drag it to another day for a quick move</span>.
      </p>

      <ScheduleItemDialog
        occurrence={selectedOccurrence}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onUpdated={onRefresh}
        workflowOptions={workflowOptions}
      />

      <AlertDialog open={Boolean(pendingMove)} onOpenChange={(open) => !open && setPendingMove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reschedule item?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingMove
                ? scheduleMoveDescription(pendingMove.occurrence.item, pendingMove.targetDate)
                : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isMoving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={isMoving}
              onClick={(event) => {
                event.preventDefault()
                void confirmMove()
              }}
            >
              {isMoving ? "Moving…" : "Confirm move"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function toOccurrence(target: ScheduledItem | ScheduleOccurrence): ScheduleOccurrence {
  if ("item" in target) return target
  const anchor =
    target.nextRunAt ||
    target.startedAt ||
    target.completedAt ||
    target.lastRunAt ||
    new Date().toISOString()
  return {
    key: `${target.id}:${anchor}`,
    item: target,
    date: new Date(anchor),
    projected: false,
  }
}

function EmptyRange({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card py-12 text-center text-sm text-muted-foreground">
      {label}
    </div>
  )
}

function ViewSkeleton({ view }: { view: ViewMode }) {
  if (view === "list") {
    return (
      <div className="space-y-2 rounded-xl border border-border bg-card p-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-2.5 w-2.5 rounded-full" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        ))}
      </div>
    )
  }
  if (view === "gantt") {
    return (
      <div className="space-y-3 rounded-xl border border-border bg-card p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-6 flex-1" />
          </div>
        ))}
      </div>
    )
  }
  return (
    <>
      {/* Mobile: week strip + agenda */}
      <div className="space-y-4 md:hidden">
        <Skeleton className="h-28 rounded-2xl" />
        <div className="space-y-3 rounded-2xl border border-border bg-card p-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-16 flex-1 rounded-xl" />
            </div>
          ))}
        </div>
      </div>
      {/* Desktop: fixed-height month board */}
      <div className="hidden rounded-2xl border border-border bg-muted/30 p-3 md:block">
        <div
          className="grid grid-cols-7 gap-2"
          style={{
            gridTemplateRows: "repeat(6, minmax(6.75rem, 1fr))",
            minHeight: "42rem",
            height: "42rem",
          }}
        >
          {Array.from({ length: 42 }).map((_, i) => (
            <Skeleton key={i} className="h-full min-h-[6.75rem] rounded-xl bg-card" />
          ))}
        </div>
      </div>
    </>
  )
}
