"use client"

import { useMemo, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { kindChipInlineStyle, kindColorVar, type ScheduleOccurrence } from "@/lib/schedules"
import { addDays, formatTime, isSameDay, startOfCalendarGrid } from "./shared"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
/** Always 6 weeks × 7 days so the grid never changes height with content or month length. */
const GRID_DAYS = 42

export function CalendarView({
  month,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
  onMoveRequest,
}: {
  month: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
  onMoveRequest?: (occurrence: ScheduleOccurrence, targetDate: Date) => void
}) {
  const reduceMotion = useReducedMotion()
  const [draggingKey, setDraggingKey] = useState<string | null>(null)
  const [dropDayKey, setDropDayKey] = useState<string | null>(null)
  const gridStart = useMemo(() => startOfCalendarGrid(month), [month])
  const days = useMemo(
    () => Array.from({ length: GRID_DAYS }, (_, i) => addDays(gridStart, i)),
    [gridStart],
  )
  const today = new Date()

  return (
    <div className="overflow-x-auto scrollbar-hide rounded-xl border border-border bg-card">
      {/* On phones a full-width 7-col grid crushes day cells to ~50px, making
          event chips unreadable. Keep a comfortable min-width and let the
          calendar scroll horizontally; go full-width from md up. */}
      <div className="min-w-[46rem] md:min-w-0">
        <div className="grid grid-cols-7 border-b border-border bg-muted/40">
          {WEEKDAYS.map((day) => (
            <div
              key={day}
              className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              {day}
            </div>
          ))}
        </div>
        {/* Fixed outer height + equal 6 rows — cells do not grow with chip count. */}
        <div className="grid h-[32rem] grid-cols-7 grid-rows-6 sm:h-[36rem] lg:h-[40rem]">
          {days.map((day, idx) => {
            const inMonth = day.getMonth() === month.getMonth()
            const dayOccurrences = occurrences.filter((o) => isSameDay(o.date, day))
            const isToday = isSameDay(day, today)
            return (
              <div
                key={idx}
                onDragOver={(event) => {
                  if (!draggingKey || !onMoveRequest) return
                  event.preventDefault()
                  setDropDayKey(String(idx))
                }}
                onDragLeave={() => setDropDayKey((current) => (current === String(idx) ? null : current))}
                onDrop={(event) => {
                  event.preventDefault()
                  if (!draggingKey || !onMoveRequest) return
                  const occurrence = occurrences.find((entry) => entry.key === draggingKey)
                  if (!occurrence) return
                  const nextDate = new Date(day)
                  nextDate.setHours(
                    occurrence.date.getHours(),
                    occurrence.date.getMinutes(),
                    occurrence.date.getSeconds(),
                    0,
                  )
                  onMoveRequest(occurrence, nextDate)
                  setDraggingKey(null)
                  setDropDayKey(null)
                }}
                className={cn(
                  "flex min-h-0 flex-col overflow-hidden border-b border-r border-border p-1.5 last:border-r-0 transition-colors",
                  idx % 7 === 6 && "border-r-0",
                  !inMonth && "bg-muted/30",
                  dropDayKey === String(idx) && "bg-primary/5 ring-1 ring-inset ring-primary/20",
                )}
              >
                <div className="mb-1 flex shrink-0 items-center justify-between px-1">
                  <span
                    className={cn(
                      "inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-xs",
                      isToday
                        ? "bg-primary font-semibold text-primary-foreground"
                        : inMonth
                          ? "text-foreground"
                          : "text-muted-foreground/60",
                    )}
                  >
                    {day.getDate()}
                  </span>
                  {dayOccurrences.length > 0 && (
                    <span className="text-[10px] font-medium text-muted-foreground">
                      {dayOccurrences.length}
                    </span>
                  )}
                </div>
                <div className="min-h-0 flex-1 space-y-1 overflow-hidden">
                  {dayOccurrences.slice(0, 3).map((occurrence, chipIdx) => {
                    const chip = kindChipInlineStyle(occurrence.item.kind)
                    const selected = occurrence.item.id === selectedId
                    return (
                      <motion.button
                        key={occurrence.key}
                        type="button"
                        draggable={Boolean(onMoveRequest) && !occurrence.item.isSample}
                        onDragStart={() => setDraggingKey(occurrence.key)}
                        onDragEnd={() => {
                          setDraggingKey(null)
                          setDropDayKey(null)
                        }}
                        onClick={() => onOpen(occurrence)}
                        title={`${occurrence.item.title} · click to reschedule or edit`}
                        initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: 0.2,
                          delay: Math.min(idx * 0.004 + chipIdx * 0.03, 0.25),
                          ease: "easeOut",
                        }}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.97 }}
                        className={cn(
                          "flex w-full items-center gap-1.5 rounded-md border-l-2 px-1.5 py-1 text-left text-xs",
                          selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                          onMoveRequest && !occurrence.item.isSample && "cursor-grab active:cursor-grabbing",
                          draggingKey === occurrence.key && "opacity-60",
                        )}
                        style={{
                          backgroundColor: chip.backgroundColor,
                          borderLeftColor: chip.borderLeftColor,
                        }}
                      >
                        <span
                          className="h-1.5 w-1.5 shrink-0 rounded-full"
                          style={{ backgroundColor: kindColorVar(occurrence.item.kind) }}
                        />
                        <span className="truncate font-medium text-foreground">
                          {occurrence.item.title}
                        </span>
                        <span className="ml-auto shrink-0 text-[10px] text-muted-foreground">
                          {formatTime(occurrence.date)}
                        </span>
                      </motion.button>
                    )
                  })}
                  {dayOccurrences.length > 3 && (
                    <button
                      type="button"
                      onClick={() => onOpen(dayOccurrences[3])}
                      className="w-full rounded px-1.5 text-left text-[10px] font-medium text-muted-foreground hover:text-foreground"
                    >
                      +{dayOccurrences.length - 3} more
                    </button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
