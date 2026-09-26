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
  addDays,
  endOfMonth,
  scheduleBoardStyle,
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
  const failedCount = useMemo(() => items.filter((item) => item.status === "failed").length, [items])

  return (
    <div className="w-full min-w-0 space-y-4">
      {/* One operating toolbar: period on the left, scope + view on the right,
          filters on a ruled line beneath. The calendar below carries the weight. */}
      <div className="w-full min-w-0 space-y-3" data-testid="schedules-toolbar">
        <div className="flex w-full min-w-0 flex-wrap items-center gap-x-4 gap-y-3">
          {view !== "list" ? (
            <div className="flex min-w-0 items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-[4px] sm:h-8 sm:w-8"
                onClick={() => shiftFocus(-1)}
                aria-label={
                  view === "calendar" && calendarScope === "day"
                    ? "Previous day"
                    : view === "calendar" && calendarScope === "week"
                      ? "Previous week"
                      : "Previous month"
                }
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-[4px] sm:h-8 sm:w-8"
                onClick={() => shiftFocus(1)}
                aria-label={
                  view === "calendar" && calendarScope === "day"
                    ? "Next day"
                    : view === "calendar" && calendarScope === "week"
                      ? "Next week"
                      : "Next month"
                }
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <h2 className="ml-2 min-w-0 truncate text-xl font-semibold tracking-[-0.02em] text-foreground sm:text-[24px]">
                {periodLabel}
              </h2>
              <Button
                variant="outline"
                size="sm"
                className="ml-3 h-10 shrink-0 rounded-[4px] px-3 sm:h-8"
                onClick={goToday}
              >
                Today
              </Button>
            </div>
          ) : (
            <h2 className="text-xl font-semibold tracking-[-0.02em] text-foreground sm:text-[24px]">All schedules</h2>
          )}

          {failedCount > 0 ? (
            <span
              className="inline-flex items-center gap-1.5 border-l-2 border-destructive pl-2 text-[13px] font-medium text-foreground"
              data-testid="schedules-exceptions"
            >
              <span className="tabular-nums">{failedCount}</span> failed
            </span>
          ) : null}

          <div className="flex w-full min-w-0 flex-wrap items-center gap-x-5 gap-y-2 sm:ml-auto sm:w-auto">
            {view === "calendar" ? (
              <div className="flex items-center gap-4" role="group" aria-label="Calendar scope">
                {CALENDAR_SCOPES.map((scope) => {
                  const active = calendarScope === scope.id
                  return (
                    <button
                      key={scope.id}
                      type="button"
                      onClick={() => setCalendarScope(scope.id)}
                      className={cn(
                        "border-b-2 py-1 text-[13px] font-medium transition-colors",
                        active
                          ? "border-[color:var(--g-text-primary)] text-foreground"
                          : "border-transparent text-muted-foreground hover:text-foreground",
                      )}
                      aria-pressed={active}
                    >
                      {scope.label}
                    </button>
                  )
                })}
              </div>
            ) : null}

            <div
              className="inline-flex items-center gap-px rounded-[4px] border border-[color:var(--g-border-default)] p-0.5"
              role="group"
              aria-label="View"
            >
              {VIEWS.map((v) => {
                const Icon = v.icon
                const active = view === v.id
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => setView(v.id)}
                    className={cn(
                      "inline-flex min-h-8 items-center gap-1.5 rounded-[2px] px-2.5 py-1 text-[13px] font-medium transition-colors",
                      active
                        ? "bg-[color:var(--g-text-primary)] text-background"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                    aria-pressed={active}
                  >
                    <Icon className="h-3.5 w-3.5 shrink-0" />
                    <span>{v.label}</span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Kind filters double as the legend. */}
        <div className="flex flex-col gap-2 border-y border-[color:var(--g-border-subtle)] py-1.5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-1" role="group" aria-label="Schedule types">
            {ALL_KINDS.map((kind) => {
              const active = activeKinds.has(kind)
              return (
                <button
                  key={kind}
                  type="button"
                  onClick={() => toggleKind(kind)}
                  className={cn(
                    "inline-flex min-h-8 items-center gap-2 rounded-[4px] px-2 text-[13px] font-medium transition-colors hover:bg-[color:var(--g-background-muted)]",
                    active ? "text-foreground" : "text-muted-foreground",
                  )}
                  aria-pressed={active}
                >
                  <KindDot kind={kind} className={cn(!active && "opacity-30")} />
                  {KIND_STYLES[kind].label}
                  <span className="tabular-nums text-muted-foreground">{counts[kind]}</span>
                </button>
              )
            })}
          </div>
          {workflowOptions && workflowOptions.length > 0 && (
            <Select
              value={workflowId ?? "all"}
              onValueChange={(v) => onWorkflowChange?.(v === "all" ? undefined : v)}
            >
              <SelectTrigger
                className="h-10 w-full shrink-0 rounded-[4px] text-xs sm:h-8 sm:w-[200px]"
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
        </div>
      </div>

      {/* Active view */}
      {loading && items.length === 0 ? (
        <ViewSkeleton view={view} />
      ) : (
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={`${view}:${calendarScope}`}
            className="min-w-0"
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

function ViewSkeleton({ view }: { view: ViewMode }) {
  if (view === "list") {
    return (
      <div
        className="flex flex-col space-y-2 overflow-hidden rounded-[var(--np-radius-md)] border border-border bg-card p-3"
        style={scheduleBoardStyle}
      >
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
      <div
        className="flex flex-col space-y-3 overflow-hidden rounded-[var(--np-radius-md)] border border-border bg-card p-4"
        style={scheduleBoardStyle}
      >
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
        <Skeleton className="h-28 rounded-[var(--np-radius-md)]" />
        <div className="space-y-3 rounded-[var(--np-radius-md)] border border-border bg-card p-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-4 w-4 rounded-full" />
              <Skeleton className="h-16 flex-1 rounded-[var(--np-radius-sm)]" />
            </div>
          ))}
        </div>
      </div>
      {/* Desktop: fixed-height board matching live month/week/day */}
      <div
        className="hidden overflow-hidden border border-[color:var(--g-border-default)] md:block"
        style={scheduleBoardStyle}
      >
        <div
          className="grid h-full grid-cols-7 gap-px bg-[color:var(--g-border-subtle)]"
          style={{ gridTemplateRows: "repeat(6, minmax(0, 1fr))" }}
        >
          {Array.from({ length: 42 }).map((_, i) => (
            <Skeleton key={i} className="h-full min-h-0 rounded-none bg-background" />
          ))}
        </div>
      </div>
    </>
  )
}
