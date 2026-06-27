"use client"

import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
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
  ScheduleLegend,
  endOfMonth,
  startOfCalendarGrid,
  startOfMonth,
} from "./shared"
import { CalendarView } from "./calendar-view"
import { GanttView } from "./gantt-view"
import { ListView } from "./list-view"
import { ScheduleDetailSheet } from "./detail-sheet"

type ViewMode = "calendar" | "gantt" | "list"

const VIEWS: { id: ViewMode; label: string; icon: typeof CalendarDays }[] = [
  { id: "calendar", label: "Calendar", icon: CalendarDays },
  { id: "gantt", label: "Gantt", icon: GanttChartSquare },
  { id: "list", label: "List", icon: ListIcon },
]

const ALL_KINDS: ScheduleKind[] = ["workflow", "task", "job"]

export function SchedulesView({ items }: { items: ScheduledItem[] }) {
  const [view, setView] = useState<ViewMode>("calendar")
  const [month, setMonth] = useState(() => startOfMonth(new Date()))
  const [activeKinds, setActiveKinds] = useState<Set<ScheduleKind>>(new Set(ALL_KINDS))
  const [selected, setSelected] = useState<ScheduledItem | null>(null)
  const [sheetOpen, setSheetOpen] = useState(false)

  const filteredItems = useMemo(
    () => items.filter((item) => activeKinds.has(item.kind)),
    [items, activeKinds],
  )

  // Calendar grid spans 6 weeks; gantt spans the month. Use the wider window
  // (calendar grid) for occurrence expansion so both views are covered.
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

  const monthStart = startOfMonth(month)
  const monthEnd = endOfMonth(month)

  const handleSelect = (target: ScheduledItem | ScheduleOccurrence) => {
    const item = "item" in target ? target.item : target
    setSelected(item)
  }
  const handleOpen = (target: ScheduledItem | ScheduleOccurrence) => {
    const item = "item" in target ? target.item : target
    setSelected(item)
    setSheetOpen(true)
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

  const monthLabel = month.toLocaleString(undefined, { month: "long", year: "numeric" })
  const counts = useMemo(() => {
    const c: Record<ScheduleKind, number> = { workflow: 0, task: 0, job: 0 }
    for (const item of filteredItems) c[item.kind] += 1
    return c
  }, [filteredItems])

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        {/* View switcher */}
        <div className="inline-flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          {VIEWS.map((v) => {
            const Icon = v.icon
            const active = view === v.id
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => setView(v.id)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
                aria-pressed={active}
              >
                <Icon className="h-4 w-4" />
                {v.label}
              </button>
            )
          })}
        </div>

        {/* Month nav (calendar + gantt) */}
        {view !== "list" && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() - 1, 1))}
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[9rem] text-center text-sm font-semibold text-foreground">
              {monthLabel}
            </span>
            <Button
              variant="outline"
              size="icon"
              className="h-8 w-8"
              onClick={() => setMonth((m) => new Date(m.getFullYear(), m.getMonth() + 1, 1))}
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => setMonth(startOfMonth(new Date()))}
            >
              Today
            </Button>
          </div>
        )}
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-3 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {ALL_KINDS.map((kind) => {
            const active = activeKinds.has(kind)
            return (
              <button
                key={kind}
                type="button"
                onClick={() => toggleKind(kind)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                  active
                    ? cn(KIND_STYLES[kind].softBg, KIND_STYLES[kind].text, KIND_STYLES[kind].border)
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
                aria-pressed={active}
              >
                <KindDot kind={kind} className={cn(!active && "opacity-40")} />
                {KIND_STYLES[kind].label}
                <span className="opacity-70">{counts[kind]}</span>
              </button>
            )
          })}
        </div>
        <ScheduleLegend className="hidden sm:flex" />
      </div>

      {/* Active view */}
      {view === "calendar" && (
        <CalendarView
          month={month}
          occurrences={occurrences}
          selectedId={selected?.id}
          onSelect={handleSelect}
          onOpen={handleOpen}
        />
      )}
      {view === "gantt" && (
        <>
          <GanttView
            rangeStart={monthStart}
            rangeEnd={monthEnd}
            occurrences={occurrences.filter(
              (o) => o.date >= monthStart && o.date <= monthEnd,
            )}
            selectedId={selected?.id}
            onSelect={handleSelect}
            onOpen={handleOpen}
          />
          {occurrences.filter((o) => o.date >= monthStart && o.date <= monthEnd).length === 0 && (
            <EmptyRange label="No scheduled items this month." />
          )}
        </>
      )}
      {view === "list" && (
        <ListView
          items={filteredItems}
          selectedId={selected?.id}
          onSelect={handleSelect}
          onOpen={handleOpen}
        />
      )}

      <p className="px-1 text-xs text-muted-foreground">
        Tip: click an item to highlight it, double-click to open full details.
      </p>

      <ScheduleDetailSheet item={selected} open={sheetOpen} onOpenChange={setSheetOpen} />
    </div>
  )
}

function EmptyRange({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-card py-12 text-center text-sm text-muted-foreground">
      {label}
    </div>
  )
}
