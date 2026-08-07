"use client"

import { useMemo } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { kindColorVar, type ScheduleOccurrence } from "@/lib/schedules"
import { addDays, formatTime, isSameDay, scheduleBoardStyle, startOfWeek } from "./shared"

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

/**
 * Seven equal-height day columns for the focused week.
 * Height stays fixed whether columns are empty or packed.
 */
export function WeekView({
  focusDate,
  occurrences,
  selectedId,
  onSelect,
  onOpen,
}: {
  focusDate: Date
  occurrences: ScheduleOccurrence[]
  selectedId?: string
  onSelect: (occurrence: ScheduleOccurrence) => void
  onOpen: (occurrence: ScheduleOccurrence) => void
}) {
  const reduceMotion = useReducedMotion()
  const weekStart = useMemo(() => startOfWeek(focusDate), [focusDate])
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)),
    [weekStart],
  )
  const today = new Date()

  return (
    <div
      className="flex w-full min-w-0 flex-col overflow-hidden rounded-2xl border border-border bg-muted/30 p-2 sm:p-3"
      style={scheduleBoardStyle}
    >
      <div className="mb-2 grid shrink-0 grid-cols-7 gap-2">
        {days.map((day, idx) => (
          <div
            key={WEEKDAYS[idx]}
            className={cn(
              "px-1 pb-1 text-center text-[11px] font-semibold uppercase tracking-[0.14em]",
              idx > 4 ? "text-muted-foreground/60" : "text-muted-foreground",
            )}
          >
            <span className="block">{WEEKDAYS[idx]}</span>
            <span
              className={cn(
                "mt-1 inline-flex h-7 min-w-7 items-center justify-center rounded-full text-sm tabular-nums",
                isSameDay(day, today)
                  ? "bg-primary font-semibold text-primary-foreground"
                  : "font-medium text-foreground",
              )}
            >
              {day.getDate()}
            </span>
          </div>
        ))}
      </div>

      <div
        className="grid min-h-0 flex-1 grid-cols-7 gap-2"
        style={{ gridTemplateRows: "minmax(0, 1fr)" }}
      >
        {days.map((day, idx) => {
          const dayOccurrences = occurrences
            .filter((o) => isSameDay(o.date, day))
            .sort((a, b) => a.date.getTime() - b.date.getTime())
          const isWeekend = idx > 4
          const isToday = isSameDay(day, today)
          return (
            <div
              key={day.toISOString()}
              className={cn(
                "flex h-full min-h-0 flex-col overflow-hidden rounded-xl border p-2",
                isWeekend ? "border-border/60 bg-card/70" : "border-border/60 bg-card",
                isToday && "border-primary/40 ring-1 ring-primary/20",
              )}
            >
              <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
                {dayOccurrences.length === 0 ? (
                  <p className="px-1 py-2 text-[11px] text-muted-foreground/70">No items</p>
                ) : (
                  dayOccurrences.map((occurrence, chipIdx) => {
                    const color = kindColorVar(occurrence.item.kind)
                    const selected = occurrence.item.id === selectedId
                    return (
                      <motion.button
                        key={occurrence.key}
                        type="button"
                        onFocus={() => onSelect(occurrence)}
                        onClick={() => onOpen(occurrence)}
                        initial={reduceMotion ? false : { opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{
                          duration: 0.18,
                          delay: Math.min(chipIdx * 0.03, 0.2),
                        }}
                        className={cn(
                          "flex w-full flex-col gap-0.5 rounded-lg px-1.5 py-1.5 text-left text-xs",
                          selected && "ring-2 ring-ring ring-offset-1 ring-offset-card",
                        )}
                        style={{
                          backgroundColor: `color-mix(in oklab, ${color} 14%, transparent)`,
                          borderLeft: `3px solid ${color}`,
                        }}
                      >
                        <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">
                          {formatTime(occurrence.date)}
                        </span>
                        <span className="truncate font-medium text-foreground">
                          {occurrence.item.title}
                        </span>
                      </motion.button>
                    )
                  })
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
