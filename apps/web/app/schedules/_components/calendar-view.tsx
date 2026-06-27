"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { KIND_STYLES, type ScheduleOccurrence } from "@/lib/schedules"
import { addDays, formatTime, isSameDay, startOfCalendarGrid } from "./shared"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

export function CalendarView({
  month,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
}: {
  month: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
}) {
  const reduceMotion = useReducedMotion()
  const gridStart = useMemo(() => startOfCalendarGrid(month), [month])
  const days = useMemo(
    () => Array.from({ length: 42 }, (_, i) => addDays(gridStart, i)),
    [gridStart],
  )
  const today = new Date()

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
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
      <div className="grid grid-cols-7">
        {days.map((day, idx) => {
          const inMonth = day.getMonth() === month.getMonth()
          const dayOccurrences = occurrences.filter((o) => isSameDay(o.date, day))
          const isToday = isSameDay(day, today)
          return (
            <div
              key={idx}
              className={cn(
                "min-h-[7rem] border-b border-r border-border p-1.5 last:border-r-0",
                idx % 7 === 6 && "border-r-0",
                !inMonth && "bg-muted/30",
              )}
            >
              <div className="mb-1 flex items-center justify-between px-1">
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
              <div className="space-y-1">
                {dayOccurrences.slice(0, 3).map((occurrence, chipIdx) => {
                  const style = KIND_STYLES[occurrence.item.kind]
                  const selected = occurrence.item.id === selectedId
                  return (
                    <motion.button
                      key={occurrence.key}
                      type="button"
                      onClick={() => onSelect(occurrence)}
                      onDoubleClick={() => onOpen(occurrence)}
                      title={`${occurrence.item.title} · double-click for details`}
                      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        duration: 0.2,
                        delay: Math.min(idx * 0.004 + chipIdx * 0.03, 0.25),
                        ease: "easeOut",
                      }}
                      whileHover={{ scale: 1.03 }}
                      whileTap={{ scale: 0.97 }}
                      className={cn(
                        "flex w-full items-center gap-1.5 rounded-md border-l-2 px-1.5 py-1 text-left text-xs",
                        style.softBg,
                        selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                      )}
                      style={{ borderLeftColor: style.color }}
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ backgroundColor: style.color }}
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
  )
}
